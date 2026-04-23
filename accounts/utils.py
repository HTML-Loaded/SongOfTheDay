from django.utils.timezone import now
from datetime import timedelta
from .services import refresh_access_token

def get_valid_access_token(user):
    profile = user.spotifyprofile

    if profile.is_token_expired():
        data = refresh_access_token(profile.refresh_token)

        profile.access_token = data["access_token"]
        profile.token_expires_at = now() + timedelta(seconds=data["expires_in"])
        profile.save()

    return profile.access_token