# user/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model

# Get the custom User model if it exists, otherwise use the default
User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    """
    A custom form for user registration.
    This form extends Django's built-in UserCreationForm to include the 'email' field.
    """
    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'Enter your email address'
        })
    )
    
    class Meta:
        model = User
        # Include all necessary fields, including the two password fields
        fields = ('username', 'email', 'password', 'password2')
        field_classes = {'username': forms.CharField}
        widgets = {
            'username': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Choose a username'
            }),
            'password': forms.PasswordInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Choose a password'
            }),
            'password2': forms.PasswordInput(attrs={
                'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
                'placeholder': 'Confirm password'
            })
        }

    def clean_email(self):
        """
        Custom validation to ensure the email is unique.
        """
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email
