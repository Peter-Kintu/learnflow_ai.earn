from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.contrib import messages
# ⭐ IMPORT ProfileImageForm from the updated forms.py
from .forms import CustomUserCreationForm, ProfileImageForm 
from django.http import JsonResponse
from django.utils.translation import gettext as _
from django.utils import timezone
from django.contrib.auth.decorators import login_required 
import json 

# Get the custom User model
User = get_user_model()

# --- Helper Functions (Preserved) ---

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
        # Redirect to the main AI tool page (using a guess for the app name)
        return redirect('aiapp:home')
    
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
    """Simple endpoint for health checks."""
    return JsonResponse({"status": "ok", "message": "Server is up and running."})

# --- Authentication Views (Preserved) ---

def register_request(request):
    """Handles user registration."""
    if request.method == "POST":
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the user in after successful registration
            login(request, user)
            messages.success(request, "Registration successful. Welcome to LearnFlow AI!")
            return redirect("aiapp:home") # Redirect to main app page
        
        # If form is invalid, messages should display errors on the form
        for field, errors in form.errors.items():
            for error in errors:
                messages.error(request, f"{field.title()}: {error}")

    else:
        # GET request: show empty form
        form = CustomUserCreationForm()
        
    return render(request, "user/register.html", {"register_form": form})

def login_request(request):
    """Handles user login."""
    if request.user.is_authenticated:
        return redirect("aiapp:home")

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
    """Handles user logout."""
    logout(request)
    messages.info(request, "You have successfully logged out.") 
    return redirect("user:login")

# --- Profile Views ---

@login_required
def my_profile_redirect(request):
    """Redirects the logged-in user to their specific profile page."""
    return redirect('user:profile_detail', username=request.user.username)

@login_required
def profile_detail(request, username):
    """
    Displays the profile of a given user.
    """
    # Fetch the User object along with its related Profile
    user_profile = get_object_or_404(User.objects.select_related('profile'), username=username)
    
    # Check if the currently logged-in user is viewing their own profile
    is_owner = (request.user == user_profile)
    
    # ⭐ UPDATE: Instantiate the form for image upload only if the user is the owner
    image_form = None
    if is_owner:
        # We pass the instance so the form can display the current file names
        image_form = ProfileImageForm(instance=user_profile.profile)

    return render(request, "user/profile_detail.html", {
        "user_profile": user_profile, 
        "is_owner": is_owner,
        "image_form": image_form, # Pass the form to the template
    })

# ⭐ NEW: View to handle the image upload POST request
@login_required
def upload_profile_image(request):
    """
    Handles the POST request for uploading or changing profile images.
    """
    if request.method != 'POST':
        return redirect('user:my_profile')

    # Use request.FILES to handle file uploads
    form = ProfileImageForm(request.POST, request.FILES, instance=request.user.profile)
    
    if form.is_valid():
        form.save()
        messages.success(request, "Your profile images have been successfully updated!")
    else:
        # If there are form errors (e.g., file size/type validation)
        for field, errors in form.errors.items():
            for error in errors:
                # Capitalize the field name for better readability in the message
                messages.error(request, f"Image Error: {field.replace('_', ' ').title()} - {error}")
    
    # Redirect back to the profile page
    return redirect('user:my_profile')


# --- API/AJAX Views (Preserved) ---

@login_required
def track_ad_click(request):
    """
    API endpoint to track an ad click, update the user's points,
    and recalculate the reward amount.
    """
    POINTS_PER_CLICK = 1 
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=405)
    
    try:
        user_profile = request.user.profile
    except Exception:
        return JsonResponse({'success': False, 'message': 'User profile not found.'}, status=400)
            
    # ⭐ 1. Increment Total Clicks (for payout threshold)
    user_profile.total_clicks += 1
    
    # ⭐ 2. Increment Points (1 point per click)
    user_profile.points += POINTS_PER_CLICK
    
    # ⭐ 3. Recalculate Reward Amount (0.5 UGX per point)
    user_profile.reward_amount = calculate_reward_amount(user_profile.points)
    
    # ⭐ 4. Save the Profile
    user_profile.save()

    # ⭐ 5. Check for Payout Threshold (10,000 clicks)
    if user_profile.total_clicks >= 10000:
        # NOTE: This is where your custom payout trigger logic would go
        pass
    
    # Return the new total points and reward amount to update the client side
    return JsonResponse({
        'success': True,
        'message': 'Ad click tracked and points awarded!',
        'points': user_profile.points,
        'reward_amount': str(user_profile.reward_amount) # Convert Decimal to string for JSON safety
    })