# user/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from .constants import ROLE_CHOICES
from .models import Profile

# Get the custom User model
User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    """
    A custom form for user registration that includes email and a role selection field.
    The form now applies Tailwind classes directly to the widgets.
    """
    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'Enter your email address'
        })
    )

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'mt-2 space-y-2'
        }),
        initial='student',
        label="I am a:"
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Check if the fields exist before attempting to access them.
        # This prevents the KeyError you were seeing.
        if 'username' in self.fields:
            self.fields['username'].widget.attrs['class'] = 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500'
            self.fields['username'].widget.attrs['placeholder'] = 'Choose a username'
        
        if 'password' in self.fields:
            self.fields['password'].widget.attrs['class'] = 'w-full px-4 py-3 bg-slate-700 text-white placeholder-gray-400 border border-slate-600 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all'
            self.fields['password'].widget.attrs['placeholder'] = 'Enter a password'
        
        if 'password2' in self.fields:
            self.fields['password2'].widget.attrs['class'] = 'w-full px-4 py-3 bg-slate-700 text-white placeholder-gray-400 border border-slate-600 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 transition-all'
            self.fields['password2'].widget.attrs['placeholder'] = 'Confirm your password'

    def clean_email(self):
        """
        Custom validation to ensure the email is unique.
        """
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email

    def save(self, commit=True):
        """
        Overrides the save method to handle saving the user and their profile's role.
        """
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']

        if commit:
            user.save()
            role = self.cleaned_data.get('role')
            if hasattr(user, 'profile'):
                user.profile.role = role
                user.profile.save()
            else:
                Profile.objects.create(user=user, role=role)
        return user

class CustomUserChangeForm(UserChangeForm):
    """
    A custom form for updating an existing user that includes role selection.
    """
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'mt-2 space-y-2'
        }),
        initial='student'
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = ('username', 'email', 'role')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Apply Tailwind classes to the default widgets
        if 'username' in self.fields:
            self.fields['username'].widget.attrs['class'] = 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500'
        if 'email' in self.fields:
            self.fields['email'].widget.attrs['class'] = 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500'

        # Populate the initial value of the role field from the user's profile
        if self.instance and self.instance.profile:
            self.fields['role'].initial = self.instance.profile.role

    def save(self, commit=True):
        """
        Overrides the save method to handle saving the user's role to their profile.
        """
        user = super().save(commit=False)
        
        if commit:
            user.save()
            role = self.cleaned_data.get('role')
            if role:
                user.profile.role = role
                user.profile.save()
        return user
