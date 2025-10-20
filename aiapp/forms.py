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

    # UPDATED: Enforce max_length=5 and clarify label/placeholder
    upload_code = forms.CharField(
        label="Teacher's Access Code (5 Digits)",
        max_length=5,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'Enter the 5-digit code',
            'required': 'true'
        })
    )

    class Meta:
        model = Quiz
        fields = ['title', 'description', 'upload_code']

    def clean_upload_code(self):
        code = self.cleaned_data.get('upload_code')

        if not code:
            raise forms.ValidationError("Please enter the 5-digit Teacher's Access Code.")

        if not code.isdigit():
            raise forms.ValidationError("The access code must be composed of 5 numeric digits.")
        
        # FIX: Explicitly enforce the required 5-digit length
        if len(code) != 5:
            raise forms.ValidationError("The access code must be exactly 5 digits long.")

        return code