from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

app_name = "user"

urlpatterns = [
    # Cold start splash page at root
    path('', views.loading_screen, name='loading'),

    # Health check endpoint
    path('ping/', views.ping, name='ping'),

    # Alias for landing page (login is your public entry point)
    path('landing/', views.login_request, name='landing'),

    # Authentication routes
    path('register/', views.register_request, name='register'),
    path('login/', views.login_request, name='login'),
    path('logout/', views.logout_request, name='logout'),

    # Password management (Preserved)
    path('password_change/', auth_views.PasswordChangeView.as_view(), name='password_change'),
    path('password_change/done/', auth_views.PasswordChangeDoneView.as_view(), name='password_change_done'),
    path('password_reset/', auth_views.PasswordResetView.as_view(), name='password_reset'),
    path('password_reset/done/', auth_views.PasswordResetDoneView.as_view(), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', auth_views.PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(), name='password_reset_complete'),

    # ⭐ CORRECTED PROFILE ROUTES
    # Redirects logged-in user to their own profile: /profile/ -> /profile/username/
    path('profile/', views.my_profile_redirect, name='my_profile'),
    # Displays the profile detail: /profile/username/ (Note: function name changed to 'profile_detail')
    path('profile/<str:username>/', views.profile_detail, name='profile_detail'),

    # ⭐ NEW AD TRACKING API
    path('track-ad-click/', views.track_ad_click, name='track_ad_click'),
]