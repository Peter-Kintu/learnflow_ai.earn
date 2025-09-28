from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import Http404, HttpResponseServerError
from django.core.exceptions import PermissionDenied
from django.urls import reverse
from django.utils import timezone
from .models import Book, Transaction
from .forms import BookForm

@login_required
def book_list(request):
    books = Book.objects.all().order_by('-created_at')
    return render(request, 'book/book_list.html', {'books': books})

@login_required
def book_detail(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    has_paid = Transaction.objects.filter(user=request.user, book=book, status='paid').exists()

    if request.method == 'POST':
        try:
            if 'confirm_payment' in request.POST:
                Transaction.objects.get_or_create(
                    user=request.user,
                    book=book,
                    defaults={'amount': book.price, 'status': 'paid', 'reference': 'manual-confirmation'}
                )
                messages.success(request, "✅ Payment confirmed! You can now access the book.")
                return redirect('books:book_detail', book_id=book_id)
            else:
                messages.warning(request, "⚠️ Payment confirmation missing. Please try again.")
        except Exception as e:
            print(f"[ERROR] Payment confirmation failed for book {book_id}: {e}")
            messages.error(request, "🚫 Something went wrong while confirming payment. Please try again or contact support.")
            return HttpResponseServerError("Internal Server Error")

    whatsapp_number = "+256 774 123456"
    return render(request, 'book/book_detail.html', {
        'book': book,
        'has_paid': has_paid,
        'whatsapp_number': whatsapp_number
    })

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
                return redirect('books:teacher_book_dashboard')
    else:
        form = BookForm()
    return render(request, 'book/book_upload.html', {'form': form})

@login_required
def teacher_book_dashboard(request):
    user_books = Book.objects.filter(uploaded_by=request.user).order_by('-created_at')
    return render(request, 'book/teacher_book_dashboard.html', {'user_books': user_books})

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
            return redirect('books:teacher_book_dashboard')
    else:
        form = BookForm(instance=book)
    return render(request, 'book/book_edit.html', {'form': form, 'book': book})

@login_required
def delete_book(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    if book.uploaded_by != request.user:
        raise PermissionDenied
    if request.method == 'POST':
        book.delete()
        messages.success(request, f'"{book.title}" has been deleted successfully.')
        return redirect('books:teacher_book_dashboard')
    return render(request, 'book/book_delete_confirm.html', {'book': book})

@login_required
def vendor_earnings(request):
    books = Book.objects.filter(uploaded_by=request.user)
    transactions = Transaction.objects.filter(book__in=books, status='paid')
    total_earned = sum(t.amount for t in transactions)
    return render(request, 'book/vendor_earnings.html', {
        'transactions': transactions,
        'total_earned': total_earned
    })

@login_required
def pay_with_card(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    if Transaction.objects.filter(user=request.user, book=book, status='paid').exists():
        messages.info(request, "✅ You've already paid for this book.")
        return redirect('books:book_detail', book_id=book_id)

    # Simulated payment gateway redirect (replace with actual SDK integration)
    tx_ref = f"{request.user.id}-{book.id}-{timezone.now().timestamp()}"
    redirect_url = request.build_absolute_uri(reverse('books:payment_callback'))
    messages.info(request, "🔗 Redirecting to payment gateway...")
    return redirect(f"https://payment-gateway.example.com/pay?tx_ref={tx_ref}&amount={book.price}&redirect_url={redirect_url}")

@login_required
def payment_callback(request):
    tx_ref = request.GET.get('tx_ref')
    status = request.GET.get('status')
    book_id = request.GET.get('book_id')

    book = get_object_or_404(Book, pk=book_id)
    if status == 'successful':
        Transaction.objects.get_or_create(
            user=request.user,
            book=book,
            defaults={'amount': book.price, 'status': 'paid', 'reference': tx_ref}
        )
        messages.success(request, "✅ Payment successful! Book unlocked.")
    else:
        messages.error(request, "🚫 Payment failed or cancelled.")
    return redirect('books:book_detail', book_id=book.id)

@login_required
def download_book(request, book_id):
    book = get_object_or_404(Book, pk=book_id)
    has_paid = Transaction.objects.filter(user=request.user, book=book, status='paid').exists()
    if not has_paid:
        raise PermissionDenied
    return redirect(book.book_file_url)