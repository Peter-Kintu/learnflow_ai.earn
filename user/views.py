# user/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout, authenticate, get_user_model
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from .forms import CustomUserCreationForm

# Get the custom or default user model
User = get_user_model()

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
            # Redirect to the user's own profile page after registration
            return redirect("user:profile", username=user.username)
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
                # Redirect to the user's own profile page after login
                return redirect("user:profile", username=user.username)
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
    return redirect("user:login")

@login_required
def profile_view(request, username):
    """
    Displays the profile information for a specific user.
    The 'username' is passed from the URL.
    """
    # Use get_object_or_404 to get the User object.
    profile_user = get_object_or_404(User, username=username)

    # Pass the fetched user object to the template context.
    context = {
        'profile_user': profile_user
    }
    
    # Render the correct template file name.
    return render(request, "user/profile_detail.html", context)
