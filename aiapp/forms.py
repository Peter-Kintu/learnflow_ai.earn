# aiapp/forms.py

from django import forms
from .models import Quiz

class QuizForm(forms.ModelForm):
    """
    A Django ModelForm for creating and updating a Quiz instance.

    This form handles the basic quiz metadata (title and description),
    along with an upload access code for admin authorization.

    It is designed to be used in conjunction with a frontend system
    that dynamically handles the creation and management of questions
    and their choices, which are then submitted as JSON data.
    """

    title = forms.CharField(
        label="Quiz Title",
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'e.g., Introduction to Python',
            'required': 'true'
        })
    )

    description = forms.CharField(
        label="Description",
        widget=forms.Textarea(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'rows': 3,
            'placeholder': 'e.g., This quiz covers the basics of Python syntax and core concepts.',
            'required': 'true'
        })
    )

    upload_code = forms.CharField(
        label="Upload Access Code",
        max_length=10,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'Enter code provided by admin',
            'required': 'true'
        })
    )

    class Meta:
        model = Quiz
        fields = ['title', 'description']

    def clean_upload_code(self):
        code = self.cleaned_data.get('upload_code')

        if not code:
            raise forms.ValidationError("Please enter the code provided by the admin to authorize your upload.")

        if not code.isdigit():
            raise forms.ValidationError("Upload access code must be numeric.")

        return code