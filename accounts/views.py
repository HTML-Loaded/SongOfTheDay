from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.conf import settings
from django.utils.timezone import now
from datetime import timedelta
from urllib.parse import urlencode
from .services import exchange_code_for_token, get_spotify_me, refresh_cached_top_items
from .models import SpotifyProfile, Profile

# Create your views here.
@login_required
def connect_spotify(request):
    if not settings.SPOTIFY_CLIENT_ID or not settings.SPOTIFY_CLIENT_SECRET:
        return redirect("account")

    params = {
        "client_id": settings.SPOTIFY_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        "scope": "streaming user-read-email user-read-private user-top-read user-read-currently-playing",
        "prompt": "consent",
    }
    auth_url = f"https://accounts.spotify.com/authorize?{urlencode(params)}"
    return redirect(auth_url)

@login_required
def spotify_callback(request):
    code = request.GET.get("code")

    if not code:
        return redirect("account")
    
    data = exchange_code_for_token(code)
    expires_at = now() + timedelta(seconds=data["expires_in"])

    profile, _ = SpotifyProfile.objects.get_or_create(user=request.user)

    profile.access_token = data.get("access_token") or ""
    profile.refresh_token = data.get("refresh_token") or profile.refresh_token
    profile.token_expires_at = expires_at

    profile.save()

    if profile.access_token:
        me = get_spotify_me(profile.access_token)
        if me.status_code == 200:
            payload = me.json() or {}
            images = payload.get("images") or []
            avatar_url = images[0].get("url") if images else ""
            profile.spotify_user_id = payload.get("id") or profile.spotify_user_id
            profile.spotify_display_name = payload.get("display_name") or profile.spotify_display_name
            profile.spotify_avatar_url = avatar_url or profile.spotify_avatar_url
            profile.save(update_fields=["spotify_user_id", "spotify_display_name", "spotify_avatar_url"])

    return redirect("account")

@login_required
def account(request):
    profile, _ = Profile.objects.get_or_create(user=request.user)
    spotify_profile, _ = SpotifyProfile.objects.get_or_create(user=request.user)
    access_token_valid = bool(spotify_profile.access_token and not spotify_profile.is_token_expired())
    can_refresh = bool(spotify_profile.refresh_token)
    connected = bool(access_token_valid or can_refresh)
    needs_reconnect = bool(spotify_profile.access_token and spotify_profile.is_token_expired() and not can_refresh)
    spotify_configured = bool(settings.SPOTIFY_CLIENT_ID and settings.SPOTIFY_CLIENT_SECRET)
    error = ""
    if not spotify_configured:
        error = "Spotify is not configured. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET in your .env."

    if connected:
        refresh_short = spotify_profile.needs_top_short_refresh()
        refresh_long = spotify_profile.needs_top_long_refresh()
        if refresh_short or refresh_long:
            refresh_cached_top_items(
                spotify_profile,
                refresh_short=refresh_short,
                refresh_long=refresh_long,
                limit=10,
            )

    if request.method == "POST":
        if request.POST.get("action") == "update_bio":
            profile.bio = (request.POST.get("bio") or "").strip()
            profile.save(update_fields=["bio"])
            return redirect("account")

        if request.POST.get("action") == "upload_avatar":
            avatar = request.FILES.get("avatar_image")
            if avatar:
                profile.avatar_image = avatar
                profile.avatar_source = "upload"
                profile.save(update_fields=["avatar_image", "avatar_source"])
            return redirect("account")

        if request.POST.get("action") == "use_spotify_avatar":
            if connected and not spotify_profile.spotify_avatar_url and spotify_profile.access_token:
                me = get_spotify_me(spotify_profile.access_token)
                if me.status_code == 200:
                    payload = me.json() or {}
                    images = payload.get("images") or []
                    spotify_profile.spotify_avatar_url = images[0].get("url") if images else ""
                    spotify_profile.spotify_user_id = payload.get("id") or spotify_profile.spotify_user_id
                    spotify_profile.spotify_display_name = payload.get("display_name") or spotify_profile.spotify_display_name
                    spotify_profile.save(update_fields=["spotify_avatar_url", "spotify_user_id", "spotify_display_name"])

            profile.avatar_source = "spotify"
            profile.save(update_fields=["avatar_source"])
            return redirect("account")

        if request.POST.get("action") == "use_uploaded_avatar":
            profile.avatar_source = "upload"
            profile.save(update_fields=["avatar_source"])
            return redirect("account")

    return render(request, "accounts/account.html", {
        "profile": profile,
        "spotify_profile": spotify_profile,
        "connected": connected,
        "needs_reconnect": needs_reconnect,
        "spotify_configured": spotify_configured,
        "error": error,
    })
