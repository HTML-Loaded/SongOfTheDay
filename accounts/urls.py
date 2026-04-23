# accounts/urls.py
from django.urls import path
from . import views

urlpatterns = [
        path("", views.spotify_settings, name="spotify_settings"),
        path("connect/", views.connect_spotify, name="connect_spotify"),
        path("callback/", views.spotify_callback, name="spotify_callback"),
]