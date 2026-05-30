from django.contrib import admin
from .models import Book, Transaction

class TransactionInline(admin.TabularInline):
    """
    Inline display of transactions related to a book.
    Useful for tracking purchases directly from the book admin view.
    """
    model = Transaction
    extra = 0
    readonly_fields = ('user', 'amount', 'currency', 'status', 'reference', 'payment_method', 'verified', 'timestamp')
    can_delete = False
    show_change_link = True

@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    """
    Customizes the display of the Book model in the admin panel.
    Includes inline transactions and vendor filtering.
    """
    list_display = ('title', 'uploaded_by', 'price', 'created_at')
    search_fields = ('title', 'uploaded_by__username')
    list_filter = ('uploaded_by', 'created_at')
    inlines = [TransactionInline]

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    """
    Admin view for tracking all book transactions.
    Useful for verifying payments, auditing vendors, and managing payouts.
    """
    list_display = ('user', 'book', 'amount', 'currency', 'status', 'verified', 'payment_method', 'timestamp')
    search_fields = ('user__username', 'book__title', 'reference')
    list_filter = ('status', 'verified', 'payment_method', 'timestamp')
    readonly_fields = ('user', 'book', 'amount', 'currency', 'status', 'reference', 'payment_method', 'verified', 'timestamp')