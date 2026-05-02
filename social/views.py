from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.views.decorators.http import require_POST

from .models import Friendship

# Create your views here.


@login_required
def friends_list(request):
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

    friends.sort(key=lambda u: (u.username or "").lower())

    pending_received = (
        Friendship.objects.filter(to_user=request.user, status="pending")
        .select_related("from_user")
        .order_by("created_at")
    )
    pending_sent = (
        Friendship.objects.filter(from_user=request.user, status="pending")
        .select_related("to_user")
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
