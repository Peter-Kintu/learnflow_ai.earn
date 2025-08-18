# video/models.py

from django.db import models
from django.contrib.auth.models import User
# Import the Quiz model from your aiapp
from aiapp.models import Quiz

class Video(models.Model):
    """
    A model to represent a video resource uploaded by a teacher.
    """
    # The title of the video
    title = models.CharField(max_length=200)
    # A brief description of the video content
    description = models.TextField()
    # The URL for the video (e.g., a YouTube embed URL)
    url = models.URLField()
    # The user (teacher) who uploaded the video
    teacher = models.ForeignKey(User, on_delete=models.CASCADE)
    # Automatically records the date and time the video was uploaded
    created_at = models.DateTimeField(auto_now_add=True)
    
    # A ManyToManyField to link videos to quizzes. 
    # This allows a single video to be associated with multiple quizzes, and
    # a single quiz to be associated with multiple videos.
    quizzes = models.ManyToManyField(Quiz, blank=True, related_name='videos')

    def __str__(self):
        """
        Returns a string representation of the video instance, which is its title.
        """
        return self.title

