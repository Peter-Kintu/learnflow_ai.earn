# user/views.py

from django.shortcuts import render, redirect , get_object_or_404
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from .forms import CustomUserCreationForm
from django.contrib.auth.models import User
from django.contrib.auth.forms import AuthenticationForm

def register_request(request):
    """
    Handles user registration.
    """
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful.")
            # Redirect to the user's profile page instead of 'core:dashboard'
            return redirect("user:profile")
        messages.error(request, "Unsuccessful registration. Invalid information.")
    else:
        form = CustomUserCreationForm()

    return render(request=request, template_name="user/register.html", context={"register_form": form})

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
                # Redirect to the user's profile page instead of 'core:dashboard'
                return redirect("user:profile")
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")

    form = AuthenticationForm()
    return render(request=request, template_name="user/login.html", context={"login_form": form})

def logout_request(request):
    """
    Handles user logout.
    """
    logout(request)
    messages.info(request, "You have successfully logged out.")
    # Redirect to the user's login page, which is in the 'user' namespace
    return redirect("user:login")

def profile_view(request):
    """
    Displays the user's profile information.
    """
    user_profile = request.user.profile
    user_profile = get_object_or_404(User, username=request.user.username)
    return render(request, "user/profile.html", {"user_profile": user_profile})
