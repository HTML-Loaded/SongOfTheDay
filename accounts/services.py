import requests
from django.conf import settings
from django.utils.timezone import now
from datetime import timedelta

def exchange_code_for_token(code):
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.SPOTIFY_REDIRECT_URI,
        },
        auth=(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET),
    )
    return response.json()


def refresh_access_token(refresh_token):
    response = requests.post(
        "https://accounts.spotify.com/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
        auth=(settings.SPOTIFY_CLIENT_ID, settings.SPOTIFY_CLIENT_SECRET),
        timeout=10,
    )
    return response.json()


def get_spotify_me(access_token: str):
    response = requests.get(
        "https://api.spotify.com/v1/me",
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10,
    )
    return response


def ensure_valid_access_token(spotify_profile):
    if spotify_profile.access_token and not spotify_profile.is_token_expired():
        return spotify_profile.access_token

    if not spotify_profile.refresh_token:
        return None

    refreshed = refresh_access_token(spotify_profile.refresh_token)
    access_token = refreshed.get("access_token")
    if not access_token:
        return None

    spotify_profile.access_token = access_token
    spotify_profile.token_expires_at = now() + timedelta(seconds=int(refreshed.get("expires_in", 3600)))
    spotify_profile.save(update_fields=["access_token", "token_expires_at"])
    return access_token


def get_spotify_top(access_token: str, kind: str, time_range: str, limit: int = 10):
    response = requests.get(
        f"https://api.spotify.com/v1/me/top/{kind}",
        params={
            "time_range": time_range,
            "limit": limit,
        },
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10,
    )
    return response


def get_spotify_currently_playing(access_token: str):
    response = requests.get(
        "https://api.spotify.com/v1/me/player/currently-playing",
        params={
            "market": "from_token",
        },
        headers={
            "Authorization": f"Bearer {access_token}",
        },
        timeout=10,
    )
    return response


def simplify_currently_playing(payload: dict) -> dict | None:
    if not payload:
        return None

    item = payload.get("item") or {}
    if not item:
        return None

    album = item.get("album") or {}
    images = album.get("images") or []
    image_url = images[0].get("url") if images else None
    artists = [a.get("name") for a in (item.get("artists") or []) if a.get("name")]

    return {
        "is_playing": bool(payload.get("is_playing")),
        "progress_ms": payload.get("progress_ms"),
        "track": {
            "id": item.get("id"),
            "name": item.get("name"),
            "artists": artists,
            "album": album.get("name"),
            "duration_ms": item.get("duration_ms"),
            "image": image_url,
            "uri": item.get("uri"),
            "external_url": (item.get("external_urls") or {}).get("spotify"),
        },
    }


def _simplify_artist(item: dict) -> dict:
    images = item.get("images") or []
    image_url = images[0].get("url") if images else None
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "image": image_url,
    }


def _simplify_track(item: dict) -> dict:
    album = item.get("album") or {}
    images = album.get("images") or []
    image_url = images[0].get("url") if images else None
    artists = [a.get("name") for a in (item.get("artists") or []) if a.get("name")]
    return {
        "id": item.get("id"),
        "name": item.get("name"),
        "artists": artists,
        "album": album.get("name"),
        "image": image_url,
        "uri": item.get("uri"),
    }


def refresh_cached_top_items(spotify_profile, refresh_short: bool, refresh_long: bool, limit: int = 10):
    access_token = ensure_valid_access_token(spotify_profile)
    if not access_token:
        return False

    updated_fields = []

    if refresh_short:
        artists_response = get_spotify_top(access_token, "artists", "short_term", limit=limit)
        tracks_response = get_spotify_top(access_token, "tracks", "short_term", limit=limit)
        if artists_response.status_code == 200 and tracks_response.status_code == 200:
            spotify_profile.top_artists_short = [_simplify_artist(a) for a in (artists_response.json().get("items") or [])]
            spotify_profile.top_tracks_short = [_simplify_track(t) for t in (tracks_response.json().get("items") or [])]
            spotify_profile.top_short_updated_at = now()
            updated_fields += ["top_artists_short", "top_tracks_short", "top_short_updated_at"]

    if refresh_long:
        artists_response = get_spotify_top(access_token, "artists", "long_term", limit=limit)
        tracks_response = get_spotify_top(access_token, "tracks", "long_term", limit=limit)
        if artists_response.status_code == 200 and tracks_response.status_code == 200:
            spotify_profile.top_artists_long = [_simplify_artist(a) for a in (artists_response.json().get("items") or [])]
            spotify_profile.top_tracks_long = [_simplify_track(t) for t in (tracks_response.json().get("items") or [])]
            spotify_profile.top_long_updated_at = now()
            updated_fields += ["top_artists_long", "top_tracks_long", "top_long_updated_at"]

    if updated_fields:
        spotify_profile.save(update_fields=updated_fields)
        return True

    return False
