from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Book
from .forms import BookForm
from django.http import Http404, HttpResponseServerError

@login_required
def book_list(request):
    """
    Renders a list of all available books.
    Fetches all Book objects from the database and passes them to the template.
    """
    books = Book.objects.all().order_by('-created_at')
    return render(request, 'book/book_list.html', {'books': books})

@login_required
def book_detail(request, book_id):
    """
    Renders the detail page for a single book.

    If the user has not paid, they will see book metadata and a prompt to contact via WhatsApp.
    If payment is confirmed (via session), the book file URL is revealed.
    """
    book = get_object_or_404(Book, pk=book_id)
    has_paid = request.session.get(f'paid_for_book_{book_id}', False)

    if request.method == 'POST':
        try:
            if 'confirm_payment' in request.POST:
                request.session[f'paid_for_book_{book_id}'] = True
                messages.success(request, "✅ Payment confirmed! You can now access the book.")
                return redirect('books:book_detail', book_id=book_id)
            else:
                messages.warning(request, "⚠️ Payment confirmation missing. Please try again.")
        except Exception as e:
            print(f"[ERROR] Payment confirmation failed for book {book_id}: {e}")
            messages.error(request, "🚫 Something went wrong while confirming payment. Please try again or contact support.")
            return HttpResponseServerError("Internal Server Error")

    whatsapp_number = "+256 774 123456"  # Replace with your actual number

    return render(request, 'book/book_detail.html', {
        'book': book,
        'has_paid': has_paid,
        'whatsapp_number': whatsapp_number
    })

@login_required
def book_upload(request):
    """
    Allows a teacher to upload a new book.

    Handles both GET and POST requests.
    Validates the upload access code manually and assigns the current user as the uploader.
    """
    if request.method == 'POST':
        form = BookForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data.get('upload_code')

            if code != "123456":  # Replace with your actual admin code
                form.add_error('upload_code', "Hmm... that code doesn’t match our records. Please check with the admin and try again. Your story deserves to be shared.")
            else:
                book = form.save(commit=False)
                book.uploaded_by = request.user
                book.save()
                messages.success(request, f'🎉 "{book.title}" has been uploaded successfully! Thank you for sharing knowledge.')
                return redirect('books:teacher_book_dashboard')
    else:
        form = BookForm()

    return render(request, 'book/book_upload.html', {'form': form})

@login_required
def teacher_book_dashboard(request):
    """
    Displays a dashboard of books uploaded by the current user.
    Filters books by the current authenticated user and renders a list for them.
    """
    user_books = Book.objects.filter(uploaded_by=request.user).order_by('-created_at')
    return render(request, 'book/teacher_book_dashboard.html', {'user_books': user_books})

@login_required
def edit_book(request, book_id):
    """
    Allows a teacher to edit an existing book.
    Verifies that the current user is the owner of the book before allowing edits.
    """
    book = get_object_or_404(Book, pk=book_id)

    if book.uploaded_by != request.user:
        raise Http404

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
    """
    Allows a teacher to delete a book.
    Verifies that the current user is the owner before deleting.
    """
    book = get_object_or_404(Book, pk=book_id)

    if book.uploaded_by != request.user:
        raise Http404

    if request.method == 'POST':
        book.delete()
        messages.success(request, f'"{book.title}" has been deleted successfully.')
        return redirect('books:teacher_book_dashboard')

    return render(request, 'book/book_delete_confirm.html', {'book': book})