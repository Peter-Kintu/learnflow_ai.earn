# aiapp/forms.py

from django import forms
from .models import Quiz

class QuizForm(forms.ModelForm):
    """
    A Django ModelForm for creating a new Quiz instance.
    
    This form handles the creation of a Quiz object by accepting
    the title and description. It is designed to work in tandem with
    the JavaScript on the frontend, which handles the dynamic
    questions and choices.
    """
    class Meta:
        model = Quiz
        fields = ['title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'e.g., Introduction to Python',
                'required': 'true'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'rows': 3,
                'placeholder': 'e.g., This quiz covers the basics of Python syntax.',
                'required': 'true'
            }),
        }