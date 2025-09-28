from django.db import models
from django.contrib.auth.models import User
from django.utils.text import slugify

class Book(models.Model):
    """
    A model to represent a book resource uploaded by a teacher.
    Includes metadata, pricing, and file access.
    """
    title = models.CharField(max_length=200)
    description = models.TextField()
    cover_image_url = models.URLField(
        max_length=500,
        default='https://placehold.co/400x600/1e293b/d1d5db?text=Book+Cover'
    )
    book_file_url = models.URLField(max_length=500)
    price = models.DecimalField(max_digits=6, decimal_places=2, default=0.00)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='books')
    created_at = models.DateTimeField(auto_now_add=True)
    slug = models.SlugField(unique=True, blank=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super(Book, self).save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} by {self.uploaded_by.get_full_name() or self.uploaded_by.username}"

class Transaction(models.Model):
    """
    Tracks payments made by users for books.
    Supports card, mobile money, and manual confirmation.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    book = models.ForeignKey(Book, on_delete=models.CASCADE)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=10, default='UGX')
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('paid', 'Paid')])
    reference = models.CharField(max_length=255)
    payment_method = models.CharField(max_length=50, default='manual')  # e.g., 'visa', 'mobile_money'
    verified = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} → {self.book.title} ({self.status})"