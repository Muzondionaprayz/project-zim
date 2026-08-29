from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, UserProfile


@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """Ensure every User has exactly one UserProfile, created alongside it."""
    if created:
        UserProfile.objects.get_or_create(user=instance)
