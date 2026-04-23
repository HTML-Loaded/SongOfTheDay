from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class SpotifyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    spotify_user_id = models.CharField(max_length=255)

    access_token = models.TextField()
    refresh_token = models.TextField()

    token_expires_at = models.DateTimeField()

    def is_token_expired(self):
        return timezone.now() >= self.token_expires_at