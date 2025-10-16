from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import CustomUserCreationForm
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.utils import timezone

# Get the custom User model
User = get_user_model()


def loading_screen(request):
    """
    Public homepage with branded loading screen.
    Replaces Render's default splash page.
    Always shows branded content first, then redirects to login once backend is ready.
    Skips loading screen for authenticated users.
    """
    if request.user.is_authenticated:
        return redirect("aiapp:home")

    # Dynamic greeting based on time of day
    current_hour = timezone.now().hour
    if current_hour < 12:
        greeting = _("Good morning!")
    elif current_hour < 18:
        greeting = _("Good afternoon!")
    else:
        greeting = _("Good evening!")

    context = {
        "app_name": "LearnFlow AI",
        "message": f"{greeting} {_('Preparing your personalized learning experience...')}",
        "redirect": True  # Always trigger redirect logic
    }
    return render(request, "user/loading.html", context)


def ping(request):
    """
    Health check endpoint for uptime monitoring and deployment verification.
    Returns a JSON response for easier integration with monitoring tools.
    """
    return JsonResponse({
        "status": "OK",
        "service": "LearnFlow AI"
    }, status=200)


def register_request(request):
    """
    Handles user registration with a custom form.
    FIXED: Now correctly passes the form with errors back to the template
           instead of overwriting it and redirecting to login page.
    """
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Registration successful.")
            return redirect("aiapp:home")
        else:
            messages.error(request, "Unsuccessful registration. Invalid information. Please see the details below.")
            return render(request, "user/register.html", {"register_form": form})

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
                return redirect("aiapp:home")
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
        return redirect('user:profile', username=request.user.username)
    return redirect("user:login")


def profile_view(request, username):
    """
    Displays the profile page for a specific user based on their username.
    """
    user_profile = get_object_or_404(User, username=username)
    return render(request, "user/profile.html", {"user_profile": user_profile})