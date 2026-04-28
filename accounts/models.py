from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class SpotifyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    spotify_user_id = models.CharField(max_length=255)

    access_token = models.TextField()
    refresh_token = models.TextField()

    token_expires_at = models.DateTimeField()
    # models.DateTimeField(null=True, blank=True)

    def is_token_expired(self):
        return timezone.now() >= self.token_expires_at
    
class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)