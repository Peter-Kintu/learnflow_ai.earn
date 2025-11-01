from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import CustomUserCreationForm
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.utils import timezone
from django.contrib.auth.decorators import login_required # ⭐ NEW IMPORT
import json # ⭐ NEW IMPORT

# Get the custom User model
User = get_user_model()


# ⭐ NEW Helper Function to Calculate Reward
def calculate_reward_amount(points):
    """
    Calculates the reward amount based on accumulated points.
    Assuming a simple rate: 1 point = UGX 10.
    """
    POINTS_TO_UGX_RATE = 10 
    reward = points * POINTS_TO_UGX_RATE
    # Round to two decimal places for currency
    return round(reward, 2)


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
    Health check endpoint for Render.
    """
    return JsonResponse({'status': 'ok'})


def register_request(request):
    """
    Handles user registration.
    """
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Create user but don't save the profile yet
            user = form.save()
            
            # Save the mobile number and set the role on the Profile object
            # The Profile is guaranteed to exist due to the post_save signal
            user.profile.mobile_number = form.cleaned_data['mobile_number']
            user.profile.role = form.cleaned_data['role']
            user.profile.save()
            
            username = form.cleaned_data.get('username')
            messages.success(request, f"Account successfully created for {username}. Please log in.")
            return redirect("user:login")
        messages.error(request, "Registration failed. Invalid information.")
    else:
        form = CustomUserCreationForm()
    
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


# ⭐ NEW: API to track ad clicks and update points/reward
@login_required
def track_ad_click(request):
    """
    API endpoint to track an ad click, grant points, and update the reward amount.
    """
    if request.method == 'POST':
        # No need to parse JSON since the body is empty, but can keep a placeholder
        # for future expansion.
        
        try:
            # Ensure the user has a profile attached
            user_profile = request.user.profile
        except:
            return JsonResponse({'success': False, 'message': 'User profile not found.'}, status=400)
            
        # 1. Increment Points
        POINTS_PER_CLICK = 100 # Adjust this value as needed
        user_profile.points += POINTS_PER_CLICK
        
        # 2. Recalculate Reward Amount
        user_profile.reward_amount = calculate_reward_amount(user_profile.points)
        
        # 3. Save the Profile
        user_profile.save()
        
        # Return the new total points and reward amount to update the client side
        return JsonResponse({
            'success': True,
            'message': 'Ad click tracked and points awarded!',
            'points': user_profile.points,
            'reward_amount': user_profile.reward_amount
        }, status=200)
    
    # Return a 405 error if not a POST request
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)