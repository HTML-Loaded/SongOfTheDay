# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
        path("", views.account, name="account"),
        path("connect/", views.connect_spotify, name="connect_spotify"),
        path("callback/", views.spotify_callback, name="spotify_callback"),
]
