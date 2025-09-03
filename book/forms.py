from django import forms
from .models import Book

class BookForm(forms.ModelForm):
    """
    A form for teachers to upload and edit new books.

    This form uses the Book model and customizes the input widgets with
    Tailwind CSS classes for a consistent look and feel.
    Includes an upload_code field to restrict unauthorized submissions.
    """
    upload_code = forms.CharField(
        max_length=10,
        required=True,
        label="Upload Access Code",
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'Enter your upload access code'
        })
    )

    class Meta:
        model = Book
        fields = ['title', 'description', 'cover_image_url', 'book_file_url', 'price']

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

    def clean_upload_code(self):
        code = self.cleaned_data.get('upload_code')
        # Replace this with your actual validation logic
        if code != 'EXPECTED_CODE':
            raise forms.ValidationError("Invalid upload access code.")
        return code