from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseServerError
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone

from aiapp.models import User
from .models import Book, Transaction
from .forms import BookForm, ReviewForm
from django.db import models
import uuid
# book/views.py (or wherever your views are)
from django.shortcuts import render, redirect
# ... other imports

def payment_callback(request):
    """
    Handles the redirect or post-request from the payment gateway.
    It should contain logic to verify the transaction status and update the database.
    """
    # Example logic:
    # 1. Get transaction reference from query params or request body.
    # 2. Query the payment gateway API to confirm the status.
    # 3. If successful, update the BookTransaction model.
    # 4. Redirect the user to the book detail page or a success page.
    
    # Placeholder for actual logic:
    # return redirect('book:payment_success')
    
    # For now, a simple placeholder redirect:
    return render(request, 'payment_success.html', {'status': 'Verification in progress...'})

# ... your existing views (like pay_with_card)

@login_required
def book_list(request):
    books = Book.objects.all().order_by('-created_at')
    query = request.GET.get('q')
    category = request.GET.get('category')
    sort = request.GET.get('sort', '-created_at')

    if query:
        books = books.filter(title__icontains=query) | books.filter(description__icontains=query)
    if category:
        books = books.filter(category=category)
    books = books.order_by(sort)

    categories = Book.CATEGORY_CHOICES
    return render(request, 'book/book_list.html', {
        'books': books,
        'categories': categories,
        'query': query,
        'selected_category': category,
        'sort': sort,
        'show_ads': True
    })

@login_required
def book_detail(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    has_paid = Transaction.objects.filter(user=request.user, book=book, status='paid', verified=True).exists()
    tx = Transaction.objects.filter(user=request.user, book=book, verified=True).order_by('-verified_at').first()
    reviews = book.reviews.all()
    user_review = reviews.filter(user=request.user).first()
    review_form = ReviewForm(instance=user_review)

    if request.method == 'POST':
        if 'confirm_payment' in request.POST:
            # ... existing payment confirmation code ...
            try:
                if 'confirm_payment' in request.POST:
                    tx, created = Transaction.objects.get_or_create(
                        user=request.user,
                        book=book,
                        defaults={
                            'amount': book.price,
                            'status': 'paid',
                            'reference': 'manual-confirmation',
                            'verified': True,
                            'verified_at': timezone.now(),
                            'payment_method': 'manual',
                            'access_code': uuid.uuid4().hex[:12].upper()
                        }
                    )
                    messages.success(request, f"✅ Payment confirmed! Your access code: {tx.access_code}")
                    return redirect('book:book_detail', book_id=book_id)
                else:
                    messages.warning(request, "⚠️ Payment confirmation missing. Please try again.")
            except Exception as e:
                print(f"[ERROR] Payment confirmation failed for book {book_id}: {e}")
                messages.error(request, "🚫 Something went wrong while confirming payment. Please try again or contact support.")
                return HttpResponseServerError("Internal Server Error")
        elif 'submit_review' in request.POST and has_paid:
            review_form = ReviewForm(request.POST, instance=user_review)
            if review_form.is_valid():
                review = review_form.save(commit=False)
                review.user = request.user
                review.book = book
                review.save()
                book.update_ratings()
                messages.success(request, "✅ Review submitted!")
                return redirect('book:book_detail', book_id=book_id)

    whatsapp_number = "+256789746493"
    return render(request, 'book/book_detail.html', {
        'book': book,
        'has_paid': has_paid,
        'whatsapp_number': whatsapp_number,
        'tx': tx,
        'reviews': reviews,
        'review_form': review_form,
        'user_review': user_review
    })

@login_required
def pay_with_airtel_qr(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    if Transaction.objects.filter(user=request.user, book=book, status='paid', verified=True).exists():
        messages.info(request, "✅ You've already paid for this book.")
        return redirect('book:book_detail', book_id=book_id)

    tx_ref = f"{request.user.id}-{book.id}-{int(timezone.now().timestamp())}"
    payment_url = request.build_absolute_uri(
        reverse('initiate_airtel_payment') + f"?tx_ref={tx_ref}&book_id={book.id}&user_id={request.user.id}"
    )
    qr_code_url = f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={payment_url}"

    return render(request, 'book/aitel.html', {
        'book': book,
        'qr_code_url': qr_code_url,
        'tx_ref': tx_ref
    })

@login_required
def initiate_airtel_payment(request):
    tx_ref = request.GET.get('tx_ref')
    book_id = request.GET.get('book_id')
    user_id = request.GET.get('user_id')

    book = get_object_or_404(Book, pk=book_id)
    user = get_object_or_404(User, pk=user_id)

    Transaction.objects.get_or_create(
        user=user,
        book=book,
        tx_ref=tx_ref,
        defaults={
            'amount': book.price,
            'status': 'pending',
            'reference': 'airtel-init',
            'payment_method': 'airtel_qr'
        }
    )

    return render(request, 'book/airtel_payment.html', {
        'book': book,
        'tx_ref': tx_ref,
        'user': user
    })

@login_required
def airtel_payment_callback(request):
    tx_ref = request.GET.get('tx_ref')
    book_id = request.GET.get('book_id')
    user_id = request.GET.get('user_id')
    status = request.GET.get('status')  # Expected to be 'successful'

    try:
        book = get_object_or_404(Book, pk=book_id)
        user = get_object_or_404(User, pk=user_id)

        tx = Transaction.objects.filter(user=user, book=book, tx_ref=tx_ref).first()
        if not tx:
            messages.error(request, "🚫 Transaction not found.")
        elif status == 'successful':
            tx.status = 'paid'
            tx.verified = True
            tx.verified_at = timezone.now()
            tx.access_code = uuid.uuid4().hex[:12].upper()
            tx.save()
            messages.success(request, f"✅ Airtel payment successful! Access code: {tx.access_code}")
        else:
            messages.error(request, "🚫 Airtel payment failed or cancelled.")
    except Exception as e:
        print(f"[ERROR] Airtel payment callback failed: {e}")
        messages.error(request, "🚫 Something went wrong during Airtel payment verification.")

    return redirect('book:book_detail', book_id=book_id)

@login_required
def book_upload(request):
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data.get('upload_code')
            if code != "123456":
                form.add_error('upload_code', "Hmm... that code doesn’t match our records. Please check with the admin and try again.")
            else:
                book = form.save(commit=False)
                book.uploaded_by = request.user
                book.save()
                messages.success(request, f'🎉 "{book.title}" has been uploaded successfully!')
                return redirect('book:teacher_book_dashboard')
    else:
        form = BookForm()
    return render(request, 'book/book_upload.html', {'form': form, 'show_ads': True})

@login_required
def teacher_book_dashboard(request):
    user_books = Book.objects.filter(uploaded_by=request.user).order_by('-created_at')
    return render(request, 'book/teacher_book_dashboard.html', {'user_books': user_books, 'show_ads': True})

@login_required
def edit_book(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    if book.uploaded_by != request.user:
        raise PermissionDenied
    if request.method == 'POST':
        form = BookForm(request.POST, instance=book)
        if form.is_valid():
            form.save()
            messages.success(request, f'"{book.title}" has been updated successfully!')
            return redirect('book:teacher_book_dashboard')
    else:
        form = BookForm(instance=book)
    return render(request, 'book/book_edit.html', {'form': form, 'book': book, 'show_ads': True})

@login_required
def delete_book(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    if book.uploaded_by != request.user:
        raise PermissionDenied
    if request.method == 'POST':
        book.delete()
        messages.success(request, f'"{book.title}" has been deleted successfully.')
        return redirect('book:teacher_book_dashboard')
    return render(request, 'book/book_delete_confirm.html', {'book': book, 'show_ads': True})

@login_required
def vendor_earnings(request):
    books = Book.objects.filter(uploaded_by=request.user)
    transactions = Transaction.objects.filter(book__in=books, status='paid', verified=True)
    total_earned = sum(t.amount for t in transactions)
    return render(request, 'book/vendor_earnings.html', {
        'transactions': transactions,
        'total_earned': total_earned,
        'show_ads': True
    })

@login_required
def pay_with_card(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    if Transaction.objects.filter(user=request.user, book=book, status='paid', verified=True).exists():
        messages.info(request, "✅ You've already paid for this book.")
        return redirect('book:book_detail', book_id=book_id)

    tx_ref = f"{request.user.id}-{book.id}-{timezone.now().timestamp()}"
    redirect_url = request.build_absolute_uri(reverse('book:payment_callback')) # <-- FIX APPLIED HERE
    messages.info(request, "🔗 Redirecting to payment gateway...")
    return redirect(f"https://payment-gateway.example.com/pay?tx_ref={tx_ref}&amount={book.price}&redirect_url={redirect_url}&book_id={book.id}")

@login_required
def payment_callback(request):
    tx_ref = request.GET.get('tx_ref')
    status = request.GET.get('status')
    book_id = request.GET.get('book_id')

    try:
        book = get_object_or_404(Book, pk=book_id)
        if status == 'successful':
            tx, created = Transaction.objects.get_or_create(
                user=request.user,
                book=book,
                defaults={
                    'amount': book.price,
                    'status': 'paid',
                    'reference': tx_ref,
                    'verified': True,
                    'verified_at': timezone.now(),
                    'payment_method': 'visa',
                    'access_code': uuid.uuid4().hex[:12].upper()
                }
            )
            messages.success(request, f"✅ Payment successful! Your access code: {tx.access_code}")
        else:
            messages.error(request, "🚫 Payment failed or was cancelled.")
    except Exception as e:
        print(f"[ERROR] Payment callback failed for book {book_id}: {e}")
        messages.error(request, "🚫 Something went wrong during payment verification.")

    return redirect('book:book_detail', book_id=book_id)
    
@login_required
def download_book(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    tx = Transaction.objects.filter(user=request.user, book=book, status='paid', verified=True).first()
    if not tx:
        messages.error(request, "🚫 You must complete payment to access this book.")
        return redirect('book:book_detail', book_id=book_id)
    return redirect(book.book_file_url)     

def generate_qr_code(data_url):
    return f"https://api.qrserver.com/v1/create-qr-code/?size=180x180&data={data_url}"

@login_required
def book_missing(request):
    messages.warning(request, "⏳ This book is being prepared. Please check back soon or contact support.")
    return render(request, 'book/book_missing.html')

@login_required
def vendor_dashboard(request):
    books = Book.objects.filter(uploaded_by=request.user)
    transactions = Transaction.objects.filter(book__in=books, status='paid', verified=True)

    monthly_data = {}
    for tx in transactions:
        month = tx.verified_at.strftime('%Y-%m')
        monthly_data.setdefault(month, 0)
        monthly_data[month] += tx.amount

    top_books = (
        transactions.values('book__title')
        .annotate(total=models.Sum('amount'))
        .order_by('-total')[:5]
    )

    return render(request, 'book/vendor_dashboard.html', {
        'monthly_data': monthly_data,
        'top_books': top_books,
        'total_earned': sum(tx.amount for tx in transactions)
    }) 

def send_whatsapp_confirmation(user, book, access_code):
    message = f"I just unlocked '{book.title}' on LearnFlow! My access code is {access_code}"
    whatsapp_url = f"https://wa.me/{user.phone_number}?text={message}"
    print(f"[WHATSAPP] Confirmation link: {whatsapp_url}")