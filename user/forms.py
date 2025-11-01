from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.contrib.auth import get_user_model
from .constants import ROLE_CHOICES
from .models import Profile
from book.models import Book
import re # Import re for mobile number validation

User = get_user_model()

INPUT_CLASSES = (
    'w-full px-4 py-3 bg-slate-900 text-gray-200 placeholder-gray-400 '
    'border border-slate-700 rounded-md focus:outline-none focus:ring-2 '
    'focus:ring-indigo-500 focus:border-transparent transition-all'
)

class LoginForm(forms.Form):
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
    # NEW: Mobile Phone Number field
    mobile_number = forms.CharField(
        max_length=20,
        required=True,
        label="Mobile Phone Number",
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'e.g., +256771234567'
        })
    )

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
        widget=forms.RadioSelect(attrs={'class': 'mt-2 space-y-2 text-gray-200'}),
        initial='student',
        label="I am a:"
    )

    teacher_code = forms.CharField(
        max_length=5,
        required=False,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'Enter your 5-digit teacher code'
        }),
        label="Teacher Verification Code"
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email', 'mobile_number', 'role',) # ADDED 'mobile_number'

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

        role_value = self.data.get('role') or self.initial.get('role')
        if role_value == 'teacher':
            self.fields['teacher_code'].required = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already in use.")
        return email
    
    # NEW: Validation for mobile number
    def clean_mobile_number(self):
        mobile_number = self.cleaned_data.get('mobile_number')
        # Simple validation: checks for digits, spaces, hyphens, and the '+' sign
        if not re.match(r'^\+?[\d\s\-\(\)]+$', mobile_number):
            raise forms.ValidationError("Please enter a valid phone number (e.g., +256771234567).")
        return mobile_number


    def clean_teacher_code(self):
        code = self.cleaned_data.get('teacher_code')
        role = self.cleaned_data.get('role')

        if role == 'teacher':
            if not code:
                raise forms.ValidationError("Please enter your teacher verification code.")
            if not code.isdigit():
                raise forms.ValidationError("Teacher code must be numeric.")
            if len(code) != 5:
                raise forms.ValidationError("Teacher code must be 5 digits.")
        return code

    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        password1 = cleaned_data.get('password1')

        if password1 and username and password1.lower() in username.lower():
            self.add_error('password1', 'The password is too similar to the username.')

        if password1 and len(password1) < 8:
            self.add_error('password1', 'This password is too short. It must contain at least 8 characters.')

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data['email']
        user._role = self.cleaned_data.get('role')
        mobile_number = self.cleaned_data.get('mobile_number') # GET NEW FIELD

        if commit:
            user.save()
            # UPDATED: Save role AND mobile_number to the Profile
            Profile.objects.update_or_create(
                user=user, 
                defaults={
                    'role': user._role,
                    'mobile_number': mobile_number, # SAVE MOBILE NUMBER
                    'points': 0, # Initialize points
                    'reward_amount': 0.00 # Initialize reward
                }
            )
        return user


# ⭐ FIX: THE MISSING ProfileImageForm CLASS
class ProfileImageForm(forms.ModelForm):
    """
    Form for updating a user's avatar and cover image.
    This class is required by user/views.py.
    """
    class Meta:
        model = Profile
        fields = ['avatar', 'cover_image']
        # Styling for file inputs
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'w-full text-gray-300 bg-slate-700 rounded-md border border-slate-600 p-2'}),
            'cover_image': forms.FileInput(attrs={'class': 'w-full text-gray-300 bg-slate-700 rounded-md border border-slate-600 p-2'}),
        }


class CustomUserChangeForm(UserChangeForm):
    role = forms.ChoiceField(
        choices=ROLE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'mt-2 space-y-2 text-gray-200'}),
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
            Profile.objects.update_or_create(user=user, defaults={'role': role})
        return user

class BookUploadForm(forms.ModelForm):
    teacher_code = forms.CharField(
        max_length=5,
        required=False,
        widget=forms.TextInput(attrs={
            'class': INPUT_CLASSES,
            'placeholder': 'Enter your 5-digit teacher code'
        }),
        label="Teacher Verification Code"
    )

    class Meta:
        model = Book
        fields = ['title', 'description', 'cover_image_url', 'book_file_url', 'price']
        widgets = {
            'title': forms.TextInput(attrs={'class': INPUT_CLASSES}),
            'description': forms.Textarea(attrs={'class': INPUT_CLASSES}),
            'cover_image_url': forms.URLInput(attrs={'class': INPUT_CLASSES}),
            'book_file_url': forms.URLInput(attrs={'class': INPUT_CLASSES}),
            'price': forms.NumberInput(attrs={'class': INPUT_CLASSES}),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.user and hasattr(self.user, 'profile') and self.user.profile.role == 'teacher':
            self.fields['teacher_code'].required = True
        else:
            self.fields['teacher_code'].widget = forms.HiddenInput()

    def clean_teacher_code(self):
        code = self.cleaned_data.get('teacher_code')
        if self.user and hasattr(self.user, 'profile') and self.user.profile.role == 'teacher':
            if not code:
                raise forms.ValidationError("Please enter your teacher verification code.")
            if not code.isdigit():
                raise forms.ValidationError("Teacher code must be numeric.")
            if len(code) != 5:
                raise forms.ValidationError("Teacher code must be 5 digits.")
        return code