from django.contrib.auth.models import User
from django.http import Http404
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.db.models import Q
from django.utils.timezone import now
from datetime import timedelta
from django.views.decorators.http import require_POST

from accounts.models import Profile, SpotifyProfile
from accounts.services import (
    get_spotify_currently_playing,
    simplify_currently_playing,
    ensure_valid_access_token,
    refresh_cached_top_items,
)
from feed.models import SongShare

from .models import Friendship


def _to_embed_url(track_input: str) -> str | None:
    track_input = (track_input or "").strip()
    if not track_input:
        return None

    if track_input.startswith("spotify:track:"):
        track_id = track_input.split(":")[-1]
        if track_id:
            return f"https://open.spotify.com/embed/track/{track_id}"
        return None

    if "open.spotify.com/track/" in track_input:
        parts = track_input.split("open.spotify.com/track/")
        if len(parts) >= 2:
            tail = parts[1].split("?")[0].strip("/")
            if tail:
                return f"https://open.spotify.com/embed/track/{tail}"

    return None

# Create your views here.


@login_required
def friends_list(request):
    friendships = (
        Friendship.objects.filter(status="accepted")
        .filter(Q(from_user=request.user) | Q(to_user=request.user))
        .select_related("from_user", "to_user", "from_user__profile", "to_user__profile", "from_user__spotifyprofile", "to_user__spotifyprofile")
        .order_by("created_at")
    )

    friends = []
    for friendship in friendships:
        friend = (
            friendship.to_user
            if friendship.from_user_id == request.user.id
            else friendship.from_user
        )
        friends.append(friend)

    friends.sort(key=lambda u: (u.username or "").lower())

    pending_received = (
        Friendship.objects.filter(to_user=request.user, status="pending")
        .select_related("from_user", "from_user__profile", "from_user__spotifyprofile")
        .order_by("created_at")
    )
    pending_sent = (
        Friendship.objects.filter(from_user=request.user, status="pending")
        .select_related("to_user", "to_user__profile", "to_user__spotifyprofile")
        .order_by("created_at")
    )

    return render(
        request,
        "social/friends_list.html",
        {
            "friends": friends,
            "pending_received": pending_received,
            "pending_sent": pending_sent,
            "success": request.GET.get("success"),
            "error": request.GET.get("error"),
        },
    )


@login_required
def friend_profile(request, username: str):
    friend = get_object_or_404(User, username=username)
    if friend.id == request.user.id:
        return redirect("account")

    is_friend = Friendship.objects.filter(status="accepted").filter(
        Q(from_user=request.user, to_user=friend)
        | Q(from_user=friend, to_user=request.user)
    ).exists()
    if not is_friend:
        raise Http404()

    profile, _ = Profile.objects.get_or_create(user=friend)
    spotify_profile = SpotifyProfile.objects.filter(user=friend).first()

    connected = False
    if spotify_profile:
        access_token_valid = bool(
            spotify_profile.access_token and not spotify_profile.is_token_expired()
        )
        can_refresh = bool(spotify_profile.refresh_token)
        connected = bool(access_token_valid or can_refresh)

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

    cutoff = now() - timedelta(hours=24)
    share = SongShare.objects.filter(user=friend, created_at__gte=cutoff).first()
    embed_url = _to_embed_url(share.track_input) if share else None

    now_playing = None
    if spotify_profile and connected:
        access_token = ensure_valid_access_token(spotify_profile)
        if access_token:
            response = get_spotify_currently_playing(access_token)
            if response.status_code == 200:
                now_playing = simplify_currently_playing(response.json() or {})

    return render(
        request,
        "social/friend_profile.html",
        {
            "friend": friend,
            "profile": profile,
            "spotify_profile": spotify_profile,
            "connected": connected,
            "share": share,
            "embed_url": embed_url,
            "now_playing": now_playing,
        },
    )


@login_required
def friend_now_playing(request, username: str):
    friend = get_object_or_404(User, username=username)
    if friend.id == request.user.id:
        raise Http404()

    is_friend = Friendship.objects.filter(status="accepted").filter(
        Q(from_user=request.user, to_user=friend)
        | Q(from_user=friend, to_user=request.user)
    ).exists()
    if not is_friend:
        raise Http404()

    spotify_profile = SpotifyProfile.objects.filter(user=friend).first()
    if not spotify_profile:
        return JsonResponse({"now_playing": None, "server_time_ms": None})

    access_token = ensure_valid_access_token(spotify_profile)
    if not access_token:
        return JsonResponse({"now_playing": None, "server_time_ms": None})

    response = get_spotify_currently_playing(access_token)
    if response.status_code == 204:
        return JsonResponse({"now_playing": None, "server_time_ms": None})
    if response.status_code != 200:
        return JsonResponse({"now_playing": None, "server_time_ms": None}, status=502)

    payload = simplify_currently_playing(response.json() or {})
    return JsonResponse({"now_playing": payload, "server_time_ms": int(now().timestamp() * 1000)})


@login_required
def friends_now_playing(request):
    friendships = (
        Friendship.objects.filter(status="accepted")
        .filter(Q(from_user=request.user) | Q(to_user=request.user))
        .select_related("from_user", "to_user")
        .order_by("created_at")
    )

    friends = []
    for friendship in friendships:
        friend = (
            friendship.to_user
            if friendship.from_user_id == request.user.id
            else friendship.from_user
        )
        friends.append(friend)

    results = {}
    server_time_ms = int(now().timestamp() * 1000)

    for friend in friends:
        cache_key = f"now_playing:user:{friend.id}"
        cached = cache.get(cache_key)
        if cached is not None:
            results[friend.username] = cached
            continue

        spotify_profile = SpotifyProfile.objects.filter(user=friend).first()
        if not spotify_profile:
            cache.set(cache_key, None, timeout=5)
            results[friend.username] = None
            continue

        access_token = ensure_valid_access_token(spotify_profile)
        if not access_token:
            cache.set(cache_key, None, timeout=5)
            results[friend.username] = None
            continue

        response = get_spotify_currently_playing(access_token)
        if response.status_code == 204:
            cache.set(cache_key, None, timeout=5)
            results[friend.username] = None
            continue
        if response.status_code != 200:
            cache.set(cache_key, None, timeout=5)
            results[friend.username] = None
            continue

        payload = simplify_currently_playing(response.json() or {})
        cache.set(cache_key, payload, timeout=5)
        results[friend.username] = payload

    return JsonResponse({"now_playing": results, "server_time_ms": server_time_ms})


@login_required
@require_POST
def send_friend_request(request):
    username = (request.POST.get("username") or "").strip()
    if not username:
        return redirect("friends_list")

    try:
        to_user = User.objects.get(username=username)
    except User.DoesNotExist:
        return redirect("friends_list")

    if to_user.id == request.user.id:
        return redirect("friends_list")

    existing = Friendship.objects.filter(
        Q(from_user=request.user, to_user=to_user)
        | Q(from_user=to_user, to_user=request.user)
    ).first()
    if existing:
        return redirect("friends_list")

    Friendship.objects.create(from_user=request.user, to_user=to_user, status="pending")
    return redirect("friends_list")


@login_required
@require_POST
def accept_friend_request(request, friendship_id: int):
    friendship = get_object_or_404(
        Friendship, id=friendship_id, to_user=request.user, status="pending"
    )
    friendship.status = "accepted"
    friendship.save(update_fields=["status"])
    return redirect("friends_list")


@login_required
@require_POST
def decline_friend_request(request, friendship_id: int):
    friendship = get_object_or_404(
        Friendship, id=friendship_id, to_user=request.user, status="pending"
    )
    friendship.delete()
    return redirect("friends_list")


@login_required
@require_POST
def cancel_friend_request(request, friendship_id: int):
    friendship = get_object_or_404(
        Friendship, id=friendship_id, from_user=request.user, status="pending"
    )
    friendship.delete()
    return redirect("friends_list")
