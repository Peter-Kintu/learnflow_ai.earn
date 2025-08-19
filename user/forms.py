from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from .models import Profile

# Get the custom User model if it exists, otherwise use the default
User = get_user_model()

class CustomUserCreationForm(UserCreationForm):
    """
    A custom form for user registration that includes email and a role selection field.
    The email field has custom validation for uniqueness.
    """
    email = forms.EmailField(
        required=True,
        label="Email Address",
        widget=forms.EmailInput(attrs={
            'class': 'w-full px-4 py-3 bg-slate-700 border border-slate-600 rounded-md text-gray-200 placeholder-gray-400 focus:outline-none focus:border-indigo-500',
            'placeholder': 'Enter your email address'
        })
    )
    
    # Add the role field to the form
    role = forms.ChoiceField(
        choices=Profile.ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={
            'class': 'mt-2 space-y-2'
        }),
        initial='student'
    )

    class Meta:
        model = User
        # Include all necessary fields in the form
        fields = ('username', 'email', 'role', 'password', 'password2')
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
