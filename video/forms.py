from django import forms
from .models import Video
from aiapp.models import Quiz

class VideoForm(forms.ModelForm):
    """
    A form for teachers to upload and add new videos, including a ManyToMany
    field for linking quizzes and a code field to restrict uploads.

    The upload_code field is required and must be numeric, but accepts any number.
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
        model = Video
        fields = ['title', 'description', 'url', 'quizzes']

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

    def clean_upload_code(self):
        code = self.cleaned_data.get('upload_code')

        if not code:
            raise forms.ValidationError("Please enter the code provided by the admin to authorize your upload.")

        if not code.isdigit():
            raise forms.ValidationError("Upload access code must be numeric.")

        return code