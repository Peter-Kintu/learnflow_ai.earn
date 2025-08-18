# books/models.py

from django.db import models
from django.contrib.auth.models import User

class Book(models.Model):
    """
    A model to represent a book resource uploaded by a teacher.
    
    This model includes fields for the book's metadata and a reference to the
    teacher who uploaded it. It also includes fields for the cover image and
    the book file itself.
    """
    # The title of the book.
    title = models.CharField(max_length=200)
    
    # A brief description of the book content.
    description = models.TextField()
    
    # The URL for the book's cover image.
    cover_image_url = models.URLField(max_length=500, default='https://placehold.co/400x600/1e293b/d1d5db?text=Book+Cover')
    
    # The URL for the book file itself. This is a placeholder for a file storage
    # system. In a real-world application, this would likely be a FileField.
    book_file_url = models.URLField(max_length=500)
    
    # The price of the book.
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    
    # The user (teacher) who uploaded the book.
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='books')
    
    # Automatically records the date and time the book was uploaded.
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        """
        Returns a string representation of the book instance, which is its title.
        """
        return self.title

