from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from .models import SpotifyProfile

@receiver(post_save, sender=User)
def create_spotify_profile(sender, instance, created, **kwargs):
    if created:
        SpotifyProfile.objects.create(user=instance)