from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils.timezone import now
from datetime import timedelta
from urllib.parse import urlencode
from .services import exchange_code_for_token
from .models import SpotifyProfile

# Create your views here.
@login_required
def connect_spotify(request):
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        profile = SpotifyProfile.objects.filter(user=request.user).first()
        return render(request, "accounts/spotify_settings.html", {
            "profile": profile,
            "connected": bool(profile and profile.access_token),
            "error": "Spotify is not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your .env.",
        })

    params = {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "scope": "streaming user-read-email",
    }
    auth_url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    return redirect(auth_url)

@login_required
def spotify_callback(request):
    code = request.GET.get("code")

    if not code:
        return redirect("spotify_settings")
    
    data = exchange_code_for_token(code)
    expires_at = now() + timedelta(seconds=data["expires_in"])

    try:
        profile = SpotifyProfile.objects.get(user=request.user)
    except SpotifyProfile.DoesNotExist:
        profile = SpotifyProfile(user=request.user)

    profile.access_token = data["access_token"]
    profile.refresh_token = data.get("refresh_token")
    profile.token_expires_at = expires_at

    profile.save()

    return redirect("spotify_settings")

@login_required
def spotify_settings(request):
    profile = SpotifyProfile.objects.filter(user=request.user).first()

    return render(request, "accounts/spotify_settings.html", {
        "profile": profile,
        "connected": bool(profile and profile.access_token)
    })
