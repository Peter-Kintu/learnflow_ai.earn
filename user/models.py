from django.db import models
from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver
from .constants import ROLE_CHOICES
from django.core.exceptions import ObjectDoesNotExist

# Get the custom User model
User = get_user_model()


class Profile(models.Model):
    """
    Extends the default Django User model by adding a role field, 
    mobile number, and image fields for a personalized profile.
    """
    # The OneToOneField creates a link between the User and Profile models.
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # The role field uses the imported choices for validation.
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    
    # Mobile Number for registration requirement
    mobile_number = models.CharField(max_length=20, blank=True, null=True, verbose_name="Mobile Phone Number")
    
    # Fields for point and reward system
    points = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Ad Click Points") 
    reward_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00, verbose_name="Reward Amount (UGX)")
    
    # ⭐ NEW: Fields for user-uploaded images
    # NOTE: You must configure MEDIA_ROOT and MEDIA_URL in your Django settings for this to work.
    avatar = models.ImageField(
        upload_to='avatars/', 
        default='avatars/default.png', 
        blank=True, 
        null=True,
        verbose_name="Profile Avatar"
    )
    cover_image = models.ImageField(
        upload_to='covers/', 
        default='covers/default_cover.jpg', 
        blank=True, 
        null=True,
        verbose_name="Cover Image"
    )

    # Field to track total ad clicks for payout calculation
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
    and ensures an existing profile is saved.
    """
    if created:
        # If a new User instance is created, a Profile is also created and linked.
        Profile.objects.create(user=instance)
    else:
        try:
            # For an existing user, we try to save their profile.
            instance.profile.save()
        except ObjectDoesNotExist:
            # Handle the case where a User exists but somehow the Profile was deleted
            Profile.objects.create(user=instance)