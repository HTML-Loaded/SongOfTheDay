from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Profile(models.Model):
    AVATAR_SOURCES = [
        ("upload", "Upload"),
        ("spotify", "Spotify"),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    bio = models.TextField(blank=True)
    avatar_image = models.ImageField(upload_to="avatars/", blank=True, null=True)
    avatar_source = models.CharField(
        max_length=20,
        choices=AVATAR_SOURCES,
        default="upload",
    )

    def get_avatar_url(self):
        if self.avatar_source == "upload" and self.avatar_image:
            try:
                return self.avatar_image.url
            except ValueError:
                return ""

        spotify_profile = getattr(self.user, "spotifyprofile", None)
        if self.avatar_source == "spotify" and spotify_profile and spotify_profile.spotify_avatar_url:
            return spotify_profile.spotify_avatar_url

        return ""

class SpotifyProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)

    spotify_user_id = models.CharField(max_length=255, blank=True, default="")
    spotify_display_name = models.CharField(max_length=255, blank=True, default="")
    spotify_avatar_url = models.URLField(blank=True, default="")

    access_token = models.TextField(blank=True, default="")
    refresh_token = models.TextField(blank=True, default="")

    token_expires_at = models.DateTimeField(null=True, blank=True)

    def is_token_expired(self):
        if not self.token_expires_at:
            return True
        return timezone.now() >= self.token_expires_at
