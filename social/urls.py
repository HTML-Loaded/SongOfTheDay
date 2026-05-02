# social/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("friends/", views.friends_list, name="friends_list"),
    path(
        "friends/request/",
        views.send_friend_request,
        name="send_friend_request",
    ),
    path(
        "friends/accept/<int:friendship_id>/",
        views.accept_friend_request,
        name="accept_friend_request",
    ),
    path(
        "friends/decline/<int:friendship_id>/",
        views.decline_friend_request,
        name="decline_friend_request",
    ),
    path(
        "friends/cancel/<int:friendship_id>/",
        views.cancel_friend_request,
        name="cancel_friend_request",
    ),
]
