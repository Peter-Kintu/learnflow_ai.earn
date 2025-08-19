# user/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from .forms import CustomUserCreationForm  # Use the correct form class name
from django.contrib.auth.forms import AuthenticationForm

def register_request(request):
    """
    Handles user registration.
    If the request method is POST, it processes the form data.
    If the request method is GET, it displays an empty registration form.
    """
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)  # Use the correct form class name
        if form.is_valid():
            user = form.save()
            # Log the user in immediately after registration
            login(request, user)
            messages.success(request, "Registration successful.")
            return redirect("core:dashboard")  # Redirect to the main dashboard after login
        messages.error(request, "Unsuccessful registration. Invalid information.")
    else:
        # If it's a GET request, create an empty form
        form = CustomUserCreationForm()  # Use the correct form class name

    # Render the registration page with the form
    return render(request=request, template_name="user/register.html", context={"register_form": form})

def login_request(request):
    """
    Handles user login.
    If the request method is POST, it processes the login credentials.
    If the request method is GET, it displays an empty login form.
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
                return redirect("core:dashboard")
            else:
                messages.error(request, "Invalid username or password.")
        else:
            messages.error(request, "Invalid username or password.")
    
    # If it's a GET request or the form is invalid, display the form
    form = AuthenticationForm()
    return render(request=request, template_name="user/login.html", context={"login_form": form})

def logout_request(request):
    """
    Handles user logout.
    Logs the user out and displays a success message.
    """
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect("core:login")

def profile_view(request):
    """
    Displays the user's profile information.
    """
    return render(request, "user/profile.html")
