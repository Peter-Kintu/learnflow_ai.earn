from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
# Import our new custom form, which we'll create next.
from .forms import UserRegistrationForm


def register(request):
    """
    Handles user registration using a custom form that includes the user role.

    If the request method is POST and the form is valid, it saves the new user
    and updates their profile with the selected role before logging them in.
    """
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            # Save the new user object
            user = form.save()
            
            # The signal we created earlier has already made a Profile for this user.
            # We just need to update the role based on the form data.
            role = form.cleaned_data.get('role')
            user.profile.role = role
            user.profile.save()

            # Log the new user in and redirect to a home page.
            login(request, user)
            return redirect('aiapp:home')  # Assuming 'aiapp:home' is the name of your home page URL
    else:
        form = UserRegistrationForm()
        
    return render(request, 'user/register.html', {'form': form})

@login_required
def profile_view(request):
    """
    A placeholder for a user profile view.
    """
    return render(request, 'user/profile.html')
