# videos/admin.py

from django.contrib import admin
from .models import Video

# Register the Video model to make it available in the Django admin interface.
@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    """
    Customizes the display of the Video model in the admin panel.
    """
    # Define the fields to display in the list view of videos.
    list_display = ('title', 'teacher', 'created_at')
    
    # Add a search bar to search for videos by title.
    search_fields = ('title',)
    
    # Enable filtering by teacher to easily find videos uploaded by a specific user.
    list_filter = ('teacher',)
