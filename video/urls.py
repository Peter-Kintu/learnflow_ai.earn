# video/urls.py

from django.urls import path
from . import views

# Define the application's namespace for use in templates.
app_name = 'video'

urlpatterns = [
    # The main URL for the video app, which will display a list of all videos
    path('', views.video_list, name='video_list'),
    
    # URL for the video detail page, capturing the video's ID as an integer.
    path('<int:video_id>/', views.video_detail, name='video_detail'),
    
    # URL for the video creation form.
    path('create/', views.create_video, name='create_video'),

    # URL for the teacher's dashboard, to manage their own content.
    path('dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    
    # URL for editing a specific video, identified by its ID.
    path('edit/<int:video_id>/', views.edit_video, name='edit_video'),

    # URL for deleting a specific video, identified by its ID.
    path('delete/<int:video_id>/', views.delete_video, name='delete_video'),
]
