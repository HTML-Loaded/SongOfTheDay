import requests
from django.conf import settings

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
