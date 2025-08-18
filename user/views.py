# user/views.py

from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm


def register(request):
    """
    Handles user registration.

    This view uses Django's built-in UserCreationForm to create a new user.
    If the request method is POST and the form is valid, it saves the new user
    and redirects them to the login page. Otherwise, it renders the registration
    form.
    """
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Log the new user in and redirect to a home page, or just redirect to login
            login(request, user)
            return redirect('aiapp:home')  # Assuming you have a home page with this name
    else:
        form = UserCreationForm()
        
    return render(request, 'user/register.html', {'form': form})

@login_required
def profile_view(request):
    """
    A placeholder for a user profile view.
    """
    return render(request, 'user/profile.html')
