# books/forms.py

from django import forms
from .models import Book

class BookForm(forms.ModelForm):
    """
    A form for teachers to upload and edit new books.
    
    This form uses the Book model and customizes the input widgets with
    Tailwind CSS classes for a consistent look and feel.
    """
    class Meta:
        model = Book
        # The fields that will be included in the form.
        fields = ['title', 'description', 'cover_image_url', 'book_file_url', 'price']
        
        # Add custom styling and attributes to form fields.
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Enter book title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Provide a brief description',
                'rows': 4
            }),
            'cover_image_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Enter the URL for the book cover image'
            }),
            'book_file_url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Enter the URL for the book file'
            }),
            'price': forms.NumberInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Enter the price (e.g., 9.99)',
                'step': '0.01'
            }),
        }
