from urllib.parse import urlparse

import requests
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.utils.timezone import now
from datetime import datetime, timedelta

from accounts.models import SpotifyProfile
from accounts.services import refresh_access_token
from social.models import Friendship
import re

from .models import SongShare, SongReaction, SongReply


def _build_share_payload(request, shares):
    rendered = []
    for share in shares:
        reaction_counts = (
            SongReaction.objects.filter(share=share)
            .values("emoji")
            .annotate(count=Count("id"))
            .order_by("-count", "emoji")
        )
        mine = set(
            SongReaction.objects.filter(share=share, user=request.user).values_list("emoji", flat=True)
        )
        rendered.append({
            "share": share,
            "embed_url": _to_embed_url(share.track_input),
            "top_reactions": list(reaction_counts[:3]),
            "has_more_reactions": reaction_counts.count() > 3,
            "mine_reactions": mine,
            "can_react": True,
        })
    return rendered


def _shares_base_queryset(request):
    cutoff = now() - timedelta(days=3)
    SongShare.objects.filter(created_at__lt=cutoff).delete()

    friendships = Friendship.objects.filter(status="accepted").filter(
        Q(from_user=request.user) | Q(to_user=request.user)
    )
    user_ids = [request.user.id]
    for friendship in friendships:
        user_ids.append(
            friendship.to_user_id
            if friendship.from_user_id == request.user.id
            else friendship.from_user_id
        )

    return (
        SongShare.objects.filter(user_id__in=user_ids, created_at__gte=cutoff)
        .select_related("user", "user__profile", "user__spotifyprofile")
        .order_by("-created_at", "-id")
    )


def _needs_spotify_connect(user) -> bool:
    profile = SpotifyProfile.objects.filter(user=user).first()
    access_ok = bool(profile and profile.access_token and not profile.is_token_expired())
    refresh_ok = bool(profile and profile.refresh_token)
    return not (access_ok or refresh_ok)


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
    cutoff = now() - timedelta(hours=24)
    tz_offset_minutes = _get_tz_offset_minutes(request)
    latest_share = SongShare.objects.filter(user=request.user).order_by("-created_at").first()
    posted_today = False
    if latest_share:
        posted_today = _local_date(latest_share.created_at, tz_offset_minutes) == _local_date(now(), tz_offset_minutes)
    if request.user.username == "Tyveksplant":
        posted_today = False
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
                share, created = SongShare.objects.get_or_create(
                    user=request.user,
                    defaults={
                        "track_input": track_input,
                        "caption": caption,
                    },
                )
                if not created:
                    share.track_input = track_input
                    share.caption = caption
                    share.created_at = now()
                    share.save(update_fields=["track_input", "caption", "created_at"])
                return redirect("feed")

    page_size = 8
    qs = _shares_base_queryset(request)
    shares = list(qs[:page_size])
    rendered = _build_share_payload(request, shares)
    next_cursor = None
    next_cursor_id = None
    if shares:
        last = shares[-1]
        next_cursor = last.created_at.isoformat()
        next_cursor_id = last.id

    return render(request, "feed/feed.html", {
        "error": error,
        "shares": rendered,
        "next_cursor": next_cursor,
        "next_cursor_id": next_cursor_id,
        "spotify_prompt": _needs_spotify_connect(request.user),
        "posted_today": posted_today,
        "wait_seconds": wait_seconds,
        "show_post_limit_popup": show_post_limit_popup,
    })


@login_required
def reactions(request, share_id: int):
    share = SongShare.objects.filter(id=share_id).first()
    if not share:
        return JsonResponse({"error": "not_found"}, status=404)

    counts = (
        SongReaction.objects.filter(share=share)
        .values("emoji")
        .annotate(count=Count("id"))
        .order_by("-count", "emoji")
    )
    mine = set(
        SongReaction.objects.filter(share=share, user=request.user).values_list("emoji", flat=True)
    )

    return JsonResponse({
        "share_id": share.id,
        "can_react": True,
        "counts": list(counts),
        "mine": list(mine),
    })


@login_required
def feed_page(request):
    page_size = int(request.GET.get("limit") or 8)
    cursor = (request.GET.get("cursor") or "").strip()
    cursor_id = (request.GET.get("cursor_id") or "").strip()

    qs = _shares_base_queryset(request)
    if cursor and cursor_id.isdigit():
        try:
            cursor_dt = datetime.fromisoformat(cursor.replace("Z", "+00:00"))
        except ValueError:
            cursor_dt = None
        if cursor_dt is not None:
            qs = qs.filter(Q(created_at__lt=cursor_dt) | (Q(created_at=cursor_dt) & Q(id__lt=int(cursor_id))))

    shares = list(qs[:page_size])
    payload = _build_share_payload(request, shares)
    html = "".join(
        render_to_string("feed/_share_card.html", {"item": item}, request=request)
        for item in payload
    )

    next_cursor = None
    next_cursor_id = None
    has_more = False
    if shares:
        last = shares[-1]
        next_cursor = last.created_at.isoformat()
        next_cursor_id = last.id
        has_more = qs.filter(
            Q(created_at__lt=last.created_at) | (Q(created_at=last.created_at) & Q(id__lt=last.id))
        ).exists()

    return JsonResponse({
        "html": html,
        "next_cursor": next_cursor,
        "next_cursor_id": next_cursor_id,
        "has_more": has_more,
    })


@login_required
def replies(request, share_id: int):
    share = SongShare.objects.filter(id=share_id).first()
    if not share:
        return JsonResponse({"error": "not_found"}, status=404)

    items = (
        SongReply.objects.filter(share=share)
        .select_related("user")
        .order_by("created_at")
    )

    return JsonResponse({
        "share_id": share.id,
        "replies": [
            {
                "id": r.id,
                "username": r.user.username,
                "body": r.body,
                "created_at": r.created_at.isoformat(),
            }
            for r in items
        ],
    })


def _sentence_count(text: str) -> int:
    parts = [p.strip() for p in re.split(r"[.!?]+", (text or "").strip()) if p.strip()]
    return len(parts)


@login_required
def reply(request, share_id: int):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    share = SongShare.objects.filter(id=share_id).first()
    if not share:
        return JsonResponse({"error": "not_found"}, status=404)

    body = (request.POST.get("body") or "").strip()
    if not body:
        return JsonResponse({"error": "invalid_body"}, status=400)

    sentences = _sentence_count(body)
    if sentences < 1 or sentences > 4:
        return JsonResponse({"error": "invalid_sentence_count"}, status=400)

    if len(body) > 900:
        return JsonResponse({"error": "invalid_body"}, status=400)

    SongReply.objects.create(share=share, user=request.user, body=body)

    items = (
        SongReply.objects.filter(share=share)
        .select_related("user")
        .order_by("created_at")
    )

    return JsonResponse({
        "share_id": share.id,
        "replies": [
            {
                "id": r.id,
                "username": r.user.username,
                "body": r.body,
                "created_at": r.created_at.isoformat(),
            }
            for r in items
        ],
    })


@login_required
def react(request, share_id: int):
    if request.method != "POST":
        return JsonResponse({"error": "method_not_allowed"}, status=405)

    share = SongShare.objects.filter(id=share_id).first()
    if not share:
        return JsonResponse({"error": "not_found"}, status=404)

    emoji = (request.POST.get("emoji") or "").strip()
    allowed = {
        "heart": "❤️",
        "laugh": "😂",
        "wow": "😮",
        "sad": "😢",
        "angry": "😡",
        "thumbs_up": "👍",
        "fire": "🔥",
        "100": "💯",
    }
    if not emoji:
        return JsonResponse({"error": "invalid_emoji"}, status=400)
    if emoji not in allowed:
        if len(emoji) > 20:
            return JsonResponse({"error": "invalid_emoji"}, status=400)
        if all(ord(ch) < 128 for ch in emoji):
            return JsonResponse({"error": "invalid_emoji"}, status=400)

    existing = SongReaction.objects.filter(share=share, user=request.user, emoji=emoji).first()
    if existing:
        existing.delete()
    else:
        SongReaction.objects.create(share=share, user=request.user, emoji=emoji)

    counts = (
        SongReaction.objects.filter(share=share)
        .values("emoji")
        .annotate(count=Count("id"))
        .order_by("-count", "emoji")
    )
    mine = set(
        SongReaction.objects.filter(share=share, user=request.user).values_list("emoji", flat=True)
    )

    return JsonResponse({
        "share_id": share.id,
        "counts": list(counts),
        "mine": list(mine),
        "emoji_map": allowed,
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
