# user/models.py

from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .constants import ROLE_CHOICES  # Import the choices from our constants file

class Profile(models.Model):
    """
    Extends the default Django User model by adding a role field.
    Each User will have a one-to-one relationship with a Profile.
    """
    # The OneToOneField creates a link between the User and Profile models.
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # The role field uses the imported choices for validation.
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')

    def __str__(self):
        """
        String representation of the Profile model.
        """
        return f'{self.user.username} Profile'

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    This signal handler automatically creates a Profile for a new User
    and saves the existing Profile whenever the User is saved.
    This combines the logic of both create and save signal handlers into one,
    making the code cleaner and more reliable.
    """
    if created:
        # If a new User instance is created, a Profile is also created and linked.
        Profile.objects.create(user=instance)
    # This line ensures the profile is saved every time the user is saved,
    # keeping the two models in sync.
    instance.profile.save()
