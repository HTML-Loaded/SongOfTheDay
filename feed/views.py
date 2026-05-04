from urllib.parse import urlparse

import requests
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils.timezone import now
from datetime import timedelta
from datetime import time as time_of_day

from accounts.models import SpotifyProfile
from accounts.services import refresh_access_token
from .models import SongShare


def _to_embed_url(track_input: str) -> str | None:
    track_input = (track_input or "").strip()
    if not track_input:
        return None

    if track_input.startswith("spotify:track:"):
        track_id = track_input.split(":")[-1]
        if track_id:
            return f"https://open.spotify.com/embed/track/{track_id}"
        return None

    try:
        parsed = urlparse(track_input)
    except ValueError:
        return None

    if parsed.netloc not in {"open.spotify.com", "www.open.spotify.com"}:
        return None

    parts = [p for p in parsed.path.split("/") if p]
    if len(parts) >= 2 and parts[0] == "track" and parts[1]:
        return f"https://open.spotify.com/embed/track/{parts[1]}"

    return None


def _get_tz_offset_minutes(request) -> int:
    raw = request.POST.get("tz_offset") or request.COOKIES.get("tz_offset")
    if raw is None:
        return 0
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 0
    if value < -840 or value > 840:
        return 0
    return value


def _local_date(dt, tz_offset_minutes: int):
    return (dt - timedelta(minutes=tz_offset_minutes)).date()


def _seconds_until_next_local_midnight(tz_offset_minutes: int) -> int:
    now_utc = now()
    local_now = now_utc - timedelta(minutes=tz_offset_minutes)
    next_midnight_local_date = local_now.date() + timedelta(days=1)
    next_midnight_local_dt = local_now.replace(
        year=next_midnight_local_date.year,
        month=next_midnight_local_date.month,
        day=next_midnight_local_date.day,
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    next_midnight_utc = next_midnight_local_dt + timedelta(minutes=tz_offset_minutes)
    seconds = int((next_midnight_utc - now_utc).total_seconds())
    return max(0, seconds)


@login_required
def feed(request):
    error = None
    tz_offset_minutes = _get_tz_offset_minutes(request)
    latest_share = SongShare.objects.filter(user=request.user).order_by("-created_at").first()
    posted_today = False
    if latest_share:
        posted_today = _local_date(latest_share.created_at, tz_offset_minutes) == _local_date(now(), tz_offset_minutes)
    wait_seconds = _seconds_until_next_local_midnight(tz_offset_minutes) if posted_today else 0
    show_post_limit_popup = False

    if request.method == "POST":
        if posted_today:
            show_post_limit_popup = True
        else:
            track_input = (request.POST.get("track_input") or "").strip()
            caption = (request.POST.get("caption") or "").strip()
            embed_url = _to_embed_url(track_input)

            if not embed_url:
                error = "Paste a Spotify track URL or a spotify:track:... URI."
            else:
                SongShare.objects.create(user=request.user, track_input=track_input, caption=caption)
                return redirect("feed")

    shares = SongShare.objects.select_related("user").all()[:20]
    rendered = []
    for share in shares:
        rendered.append({
            "share": share,
            "embed_url": _to_embed_url(share.track_input),
        })

    return render(request, "feed/feed.html", {
        "error": error,
        "shares": rendered,
        "posted_today": posted_today,
        "wait_seconds": wait_seconds,
        "show_post_limit_popup": show_post_limit_popup,
    })


@login_required
def spotify_search(request):
    query = (request.GET.get("q") or "").strip()
    if not query:
        return JsonResponse({"tracks": []})

    profile = SpotifyProfile.objects.filter(user=request.user).first()
    if not profile or not profile.access_token:
        return JsonResponse({"error": "not_connected"}, status=401)

    if profile.is_token_expired() and profile.refresh_token:
        refreshed = refresh_access_token(profile.refresh_token)
        access_token = refreshed.get("access_token")
        if access_token:
            profile.access_token = access_token
            profile.token_expires_at = now() + timedelta(seconds=int(refreshed.get("expires_in", 3600)))
            profile.save(update_fields=["access_token", "token_expires_at"])
        else:
            return JsonResponse({"error": "token_refresh_failed"}, status=401)

    response = requests.get(
        "https://api.spotify.com/v1/search",
        params={
            "q": query,
            "type": "track",
            "limit": 8,
        },
        headers={
            "Authorization": f"Bearer {profile.access_token}",
        },
        timeout=10,
    )

    if response.status_code != 200:
        return JsonResponse({"error": "spotify_error"}, status=502)

    payload = response.json() or {}
    items = ((payload.get("tracks") or {}).get("items") or [])
    tracks = []

    for item in items:
        album = item.get("album") or {}
        images = album.get("images") or []
        image_url = images[0].get("url") if images else None
        artists = ", ".join([(a.get("name") or "") for a in (item.get("artists") or []) if a.get("name")])
        tracks.append({
            "id": item.get("id"),
            "name": item.get("name"),
            "artists": artists,
            "album": album.get("name"),
            "image": image_url,
            "uri": item.get("uri"),
        })

    return JsonResponse({"tracks": tracks})
