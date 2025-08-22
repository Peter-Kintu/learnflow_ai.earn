# user/forms.py
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
    """
    A simple login form with a username and password.
    """
    username = forms.CharField(
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'Enter your username'
        })
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': f'{INPUT_CLASSES} pr-10', # Added padding for the eye icon
            'placeholder': 'Enter your password'
        })
    )

class CustomUserCreationForm(UserCreationForm):
    """
    A custom form for user registration that includes email and a role selection field.
    The form now applies consistent Tailwind classes directly to the widgets.
    """
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
        # Apply the consistent classes to the other fields
        if 'username' in self.fields:
            self.fields['username'].widget.attrs['class'] = INPUT_CLASSES
            self.fields['username'].widget.attrs['placeholder'] = 'Choose a username'
        
        if 'password' in self.fields:
            # Add pr-10 class for the eye icon, but keep the rest consistent
            self.fields['password'].widget.attrs['class'] = f'{INPUT_CLASSES} pr-10'
            self.fields['password'].widget.attrs['placeholder'] = 'Enter a password'
        
        if 'password2' in self.fields:
            # Add pr-10 class for the eye icon, but keep the rest consistent
            self.fields['password2'].widget.attrs['class'] = f'{INPUT_CLASSES} pr-10'
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
        # Apply consistent Tailwind classes to the default widgets
        if 'username' in self.fields:
            self.fields['username'].widget.attrs['class'] = INPUT_CLASSES
        if 'email' in self.fields:
            self.fields['email'].widget.attrs['class'] = INPUT_CLASSES

        # Populate the initial value of the role field from the user's profile
        if self.instance and hasattr(self.instance, 'profile'):
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
