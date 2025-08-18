# user/urls.py

from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

# Define the application namespace for user-related URLs
app_name = 'user'

urlpatterns = [
    # URL for the user registration page
    path('register/', views.register, name='register'),
    
    # URL for the user login page
    path('login/', auth_views.LoginView.as_view(template_name='user/login.html'), name='login'),
    
    # URL for the user logout page
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
]
