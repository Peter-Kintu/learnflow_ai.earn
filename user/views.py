# user/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import CustomUserCreationForm

# Get the custom User model
User = get_user_model()

def register_request(request):
    """
    Handles user registration with a custom form.
    """
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful.")
            # Redirect to the user's profile page after successful registration
            return redirect("user:my_profile")
        messages.error(request, "Unsuccessful registration. Invalid information.")
    form = CustomUserCreationForm()
    return render(request, "user/register.html", {"register_form": form})

def login_request(request):
    """
    Handles user login using the built-in AuthenticationForm.
    """
    if request.method == "POST":
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                messages.info(request, f"You are now logged in as {username}.")
                # Redirect to the user's profile page after login
                return redirect("user:my_profile")
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    form = AuthenticationForm()
    return render(request, "user/login.html", {"login_form": form})

def logout_request(request):
    """
    Handles user logout.
    """
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect("user:login")

def my_profile_redirect(request):
    """
    A view to handle redirection to the authenticated user's profile.
    This is useful for providing a generic "my profile" link.
    """
    if request.user.is_authenticated:
        # Redirects to the 'profile_view' with the current user's username
        return redirect('user:profile', username=request.user.username)
    # Redirect to login if not authenticated
    return redirect("user:login")

def profile_view(request, username):
    """
    Displays the profile page for a specific user based on their username.
    """
    # Fetch the user object or return a 404 error if not found
    user_profile = get_object_or_404(User, username=username)
    return render(request, "user/profile.html", {"user_profile": user_profile})
