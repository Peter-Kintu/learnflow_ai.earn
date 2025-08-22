# user/forms.py

from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
# Import ROLE_CHOICES directly from the constants file
from .constants import ROLE_CHOICES

# Get the custom User model if it exists, otherwise use the default
User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    """
    A custom form for user registration that explicitly defines all fields
    to ensure compatibility with custom template filters.
    """
    # Override the default username field to apply a custom widget
    username = forms.CharField(
        label="Username",
        max_length=150,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'Choose a username'
        })
    )

    # Add the custom email field
    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'Enter your email address'
        })
    )
    
    # Override the parent's password fields to apply custom widgets
    # This is a crucial step to make them compatible with the 'add_class' filter
    password = forms.CharField(
        label="Password",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'Choose a password'
        })
    )
    
    password2 = forms.CharField(
        label="Password confirmation",
        widget=forms.PasswordInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'Confirm password'
        })
    )

    # Add the custom role field, using the imported choices
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'mt-2 space-y-2'
        }),
        initial='student'
    )

    class Meta(UserCreationForm.Meta):
        model = User
        # The fields tuple now explicitly lists all the fields we've defined on the class
        fields = ('username', 'email', 'password', 'password2', 'role',)

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
        # Save the user first
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']

        if commit:
            user.save()
            # The signal we created earlier has already made a Profile for this user.
            # We just need to update the role based on the form data.
            role = self.cleaned_data.get('role')
            user.profile.role = role
            user.profile.save()
        return user

class CustomUserChangeForm(UserChangeForm):
    """
    A custom form for updating an existing user that includes role selection.
    """
    # Add the custom role field
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'mt-2 space-y-2'
        }),
        initial='student'
    )
    
    class Meta(UserChangeForm.Meta):
        model = User
        # Extend the parent's fields list to include our custom role field
        fields = UserChangeForm.Meta.fields + ('role',)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate the initial value of the role field from the user's profile
        if self.instance and self.instance.profile:
            self.fields['role'].initial = self.instance.profile.role

    def save(self, commit=True):
        """
        Overrides the save method to handle saving the user's role to their profile.
        """
        # Save the user first using the parent's save method
        user = super().save(commit=False)
        
        if commit:
            user.save()
            # Update the user's profile role based on the form data
            role = self.cleaned_data.get('role')
            if role:
                user.profile.role = role
                user.profile.save()
        return user
