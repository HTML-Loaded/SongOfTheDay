from django.shortcuts import render
from django.contrib.auth.forms import UserCreationForm
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.models import User
from django import forms

from accounts.models import SpotifyProfile

# Create your views here.
class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    def clean_username(self):
        username = (self.cleaned_data.get("username") or "").strip()
        if not username:
            return username
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def save(self, commit=True):
        user = super().save(commit=False)
        user.username = (self.cleaned_data.get("username") or "").strip()
        user.email = (self.cleaned_data.get("email") or "").strip()
        if commit:
            user.save()
        return user

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")


class SignUpView(CreateView):
    form_class = CustomUserCreationForm
    success_url = reverse_lazy("login")
    template_name = "registration/signup.html"

def home(request):
    spotify_prompt = False
    if request.user.is_authenticated:
        profile = SpotifyProfile.objects.filter(user=request.user).first()
        access_ok = bool(profile and profile.access_token and not profile.is_token_expired())
        refresh_ok = bool(profile and profile.refresh_token)
        spotify_prompt = not (access_ok or refresh_ok)
    return render(request, "home.html", {"spotify_prompt": spotify_prompt})
