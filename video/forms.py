# video/forms.py

from django import forms
from .models import Video
from aiapp.models import Quiz

class VideoForm(forms.ModelForm):
    """
    A form for teachers to upload and add new videos, including a ManyToMany
    field for linking quizzes.
    """
    class Meta:
        model = Video
        # The fields that will be included in the form.
        fields = ['title', 'description', 'url', 'quizzes']
        
        # Add custom styling and attributes to form fields.
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Enter video title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Provide a brief description',
                'rows': 4
            }),
            'url': forms.URLInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Enter the YouTube video embed URL'
            }),
            'quizzes': forms.SelectMultiple(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 focus:outline-none focus:border-indigo-500'
            })
        }
