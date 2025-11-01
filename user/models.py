from django.db import models
from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver
from .constants import ROLE_CHOICES  # Import the choices from our constants file
from django.core.exceptions import ObjectDoesNotExist

class Profile(models.Model):
    """
    Extends the default Django User model by adding a role field.
    Each User will have a one-to-one relationship with a Profile.
    """
    # The OneToOneField creates a link between the User and Profile models.
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # The role field uses the imported choices for validation.
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    
    # Mobile Number for registration requirement
    mobile_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Mobile Phone Number")
    
    # Fields for point and reward system
    points = models.IntegerField(default=0, verbose_name="Ad Click Points")
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Reward Amount (UGX)")
    
    # ⭐ NEW: Field to track total ad clicks for payout calculation
    total_clicks = models.IntegerField(default=0, verbose_name="Total Clicks")

    def __str__(self):
        """
        String representation of the Profile model.
        """
        return f'{self.user.username} Profile'

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    """
    This signal handler automatically creates a Profile for a new User
    and ensures an existing profile is saved. This is the robust and
    recommended way to handle this logic.
    """
    if created:
        # If a new User instance is created, a Profile is also created and linked.
        Profile.objects.create(user=instance)
    else:
        try:
            # For an existing user, we try to save their profile.
            # This will work for users who already have a profile.
            instance.profile.save()
        except ObjectDoesNotExist:
            # Handle the case where a User exists but no Profile was created (e.g., manual creation)
            Profile.objects.create(user=instance)