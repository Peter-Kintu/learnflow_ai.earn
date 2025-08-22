# user/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.contrib import messages
from .forms import NewUserForm

def register_request(request):
    """
    Handles user registration.
    """
    if request.method == "POST":
        form = NewUserForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful.")
            return redirect("user:my_profile")
        messages.error(request, "Unsuccessful registration. Invalid information.")
    form = NewUserForm()
    return render(request, "user/register.html", {"register_form": form})

def login_request(request):
    """
    Handles user login.
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
    Redirects the logged-in user to their specific profile URL.
    This view is a new addition to handle the URL /user/profile/
    """
    if request.user.is_authenticated:
        return redirect('user:profile', username=request.user.username)
    # Redirect to login if not authenticated
    return redirect("user:login")

def profile_view(request, username):
    """
    Displays the profile page for a specific user.
    """
    # This view is now called with a username, solving the original TypeError.
    # It fetches the user object and renders the profile template.
    user_profile = get_object_or_404(User, username=username)
    return render(request, "user/profile.html", {"user_profile": user_profile})
