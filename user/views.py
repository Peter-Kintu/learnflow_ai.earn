from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
from .forms import CustomUserCreationForm
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.utils import timezone
from django.contrib.auth.decorators import login_required 
import json 

# Get the custom User model
User = get_user_model()


# ⭐ UPDATED Helper Function to Calculate Reward (1 UGX per 2 points/clicks)
def calculate_reward_amount(points):
    """
    Calculates the reward amount based on accumulated points.
    Rate: 1 UGX for every 2 points (0.5 UGX per point).
    """
    POINTS_TO_UGX_RATE = 0.5 # 1 UGX / 2 points = 0.5 UGX per point
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
        # Redirect to the main application page
        return redirect("aiapp:home")
    
    # Dynamic greeting based on time of day
    current_hour = timezone.now().hour
    if current_hour < 12:
        greeting = _("Good morning!")
    elif current_hour < 18:
        greeting = _("Good afternoon!")
    else:
        greeting = _("Good evening!")
        
    return render(request, 'user/loading.html', {'greeting': greeting})


def ping(request):
    """ Health check endpoint """
    return JsonResponse({"status": "ok", "message": "Server is up and running."})


def register_request(request):
    """ Handles user registration. """
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            # Create the User
            user = form.save()
            
            # Get the role and mobile number from the form
            role = form.cleaned_data.get('role')
            mobile_number = form.cleaned_data.get('mobile_number')
            
            # Update the user's profile with role and mobile number
            # This logic relies on the post_save signal in models.py to create the profile first
            # The signal handler ensures instance.profile exists, so we use update_or_create for safety
            # If the profile was created via signal, we update it here.
            user.profile.role = role
            user.profile.mobile_number = mobile_number
            user.profile.save() # Manually save the profile after setting fields
            
            messages.success(request, "Registration successful. You can now log in.")
            return redirect("user:login")
        messages.error(request, "Unsuccessful registration. Invalid information provided.")
    else:
        form = CustomUserCreationForm()
        
    return render(request, "user/register.html", {"register_form": form})


def login_request(request):
    """ Handles user login. """
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
    """ Handles user logout. """
    logout(request)
    messages.info(request, "You have successfully logged out.")
    return redirect("user:login")


@login_required
def my_profile_redirect(request):
    """ Redirects to the user's own profile page. """
    return redirect('user:profile_detail', username=request.user.username)


@login_required
def profile_detail(request, username):
    """ Displays the profile details for a specific user. """
    # ⭐ FIX: Use select_related to efficiently fetch the related Profile data 
    # This helps ensure the latest profile data is available.
    user_profile = get_object_or_404(
        User.objects.select_related('profile'), # Use select_related to fetch Profile data efficiently
        username=username
    )
    
    # Check if the fetched user is the request user (for context/permissions if needed)
    is_owner = request.user == user_profile
    
    # The template uses user_profile (which is the User instance) to access profile data via user_profile.profile
    return render(request, "user/profile_detail.html", {"user_profile": user_profile, "is_owner": is_owner})


# ⭐ UPDATED: API to track ad clicks and update points/reward
@login_required
def track_ad_click(request):
    """
    API endpoint to track an ad click, grant points, and update the reward amount.
    """
    if request.method == 'POST':
        
        try:
            # Ensure the user has a profile attached
            user_profile = request.user.profile
        except:
            return JsonResponse({'success': False, 'message': 'User profile not found.'}, status=400)
            
        # ⭐ 1. Increment Total Clicks (for payout threshold)
        user_profile.total_clicks += 1
        
        # ⭐ 2. Increment Points (1 point per click)
        POINTS_PER_CLICK = 1 
        user_profile.points += POINTS_PER_CLICK
        
        # ⭐ 3. Recalculate Reward Amount (0.5 UGX per point)
        user_profile.reward_amount = calculate_reward_amount(user_profile.points)
        
        # ⭐ 4. Save the Profile
        user_profile.save()

        # ⭐ 5. Check for Payout Threshold (10,000 clicks)
        if user_profile.total_clicks >= 10000:
            # NOTE: This is where your custom payout trigger logic would go
            # Example: Trigger payout and reset relevant fields:
            # Payouts.record_payout(user_profile.user, user_profile.reward_amount)
            # user_profile.points = 0
            # user_profile.reward_amount = 0.00
            # user_profile.total_clicks = 0
            # user_profile.save()
            pass
        
        # Return the new total points and reward amount to update the client side
        return JsonResponse({
            'success': True,
            'message': 'Ad click tracked and points awarded!',
            'points': user_profile.points,
            'reward_amount': user_profile.reward_amount
        }, status=200)
    
    # Return a 405 error if not a POST request
    return JsonResponse({'success': False, 'message': 'Method not allowed.'}, status=405)