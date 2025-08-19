from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

# Create a tuple of choices for the user's role.
# This makes sure we only use 'Student' or 'Teacher' for the role.
ROLE_CHOICES = (
    ('student', 'Student'),
    ('teacher', 'Teacher'),
)

class Profile(models.Model):
    """
    Extends the default Django User model by adding a role field.
    Each User will have a one-to-one relationship with a Profile.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')

    def __str__(self):
        return f'{self.user.username} Profile'


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    Signal handler that automatically creates a Profile for each new User.
    This ensures that every user has a profile, and you don't have to
    manually create one.
    """
    if created:
        Profile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    Signal handler to save the Profile whenever the associated User is saved.
    This keeps the two models in sync.
    """
    instance.profile.save()
