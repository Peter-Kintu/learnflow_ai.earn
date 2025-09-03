from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from .constants import ROLE_CHOICES
from .models import Profile

# Get the custom User model
User = get_user_model()

# Define the common classes for all text inputs to ensure consistency
INPUT_CLASSES = 'w-full px-4 py-3 bg-slate-900 text-gray-200 placeholder-gray-400 border border-slate-700 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent transition-all'

class LoginForm(forms.Form):
    """A simple login form with a username and password."""
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'Enter your username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': f'{INPUT_CLASSES} pr-10',
            'placeholder': 'Enter your password'
        })
    )

class CustomUserCreationForm(UserCreationForm):
    """Custom registration form with email and role selection."""
    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'Enter your email address'
        })
    )

    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'mt-2 space-y-2 text-gray-200'
        }),
        initial='student',
        label="I am a:"
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'role',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'class': INPUT_CLASSES,
            'placeholder': 'Choose a username'
        })
        self.fields['password1'].widget.attrs.update({
            'class': f'{INPUT_CLASSES} pr-10',
            'placeholder': 'Enter a password'
        })
        self.fields['password2'].widget.attrs.update({
            'class': f'{INPUT_CLASSES} pr-10',
            'placeholder': 'Confirm your password'
        })

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')

        # Reassign form-level errors to specific fields
        if self.errors.get('__all__'):
            for error in self.errors['__all__']:
                if "password" in error.lower() and "match" in error.lower():
                    self.add_error('password2', error)
            del self.errors['__all__']

        if password1 and username and password1.lower() in username.lower():
            self.add_error('password1', 'The password is too similar to the username.')

        if password1 and len(password1) < 8:
            self.add_error('password1', 'This password is too short. It must contain at least 8 characters.')

        return cleaned_data

    def save(self, commit=True):
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
    """Custom form for updating user with role selection."""
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
        self.fields['username'].widget.attrs['class'] = INPUT_CLASSES
        self.fields['email'].widget.attrs['class'] = INPUT_CLASSES

        if self.instance and hasattr(self.instance, 'profile'):
            self.fields['role'].initial = self.instance.profile.role

    def save(self, commit=True):
        user = super().save(commit=False)

        if commit:
            user.save()
            role = self.cleaned_data.get('role')
            if role:
                user.profile.role = role
                user.profile.save()
        return user