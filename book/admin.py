# books/admin.py

from django.contrib import admin
from .models import Book

# Register the Book model to make it available in the Django admin interface.
@admin.register(Book)
class BookAdmin(admin.ModelAdmin):
    """
    Customizes the display of the Book model in the admin panel.
    
    This configuration is based on the provided books/models.py, using
    the 'uploaded_by' field for filtering and display.
    """
    # Define the fields to display in the list view of books.
    list_display = ('title', 'uploaded_by', 'created_at')
    
    # Add a search bar to search for books by title.
    search_fields = ('title',)
    
    # Enable filtering by the user who uploaded the book and the creation date.
    list_filter = ('uploaded_by', 'created_at')
