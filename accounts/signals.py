from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import SpotifyProfile, Profile

@receiver(post_save, sender=User)
def create_profiles(sender, instance, created, **kwargs):
    if not created:
        return

    Profile.objects.get_or_create(user=instance)
    SpotifyProfile.objects.get_or_create(user=instance)
