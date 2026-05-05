from datetime import timedelta

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now

from social.models import Friendship
from .models import SongShare


class FeedTests(TestCase):
    def test_share_replaces_existing(self):
        user = User.objects.create_user(username="u1", password="pw")
        share = SongShare.objects.create(user=user, track_input="spotify:track:old", caption="old")
        share.created_at = now() - timedelta(days=1)
        share.save(update_fields=["created_at"])

        self.client.login(username="u1", password="pw")
        response = self.client.post(
            reverse("feed"),
            {
                "track_input": "spotify:track:new",
                "caption": "new",
            },
        )
        self.assertEqual(response.status_code, 302)

        self.assertEqual(SongShare.objects.filter(user=user).count(), 1)
        updated = SongShare.objects.get(user=user)
        self.assertEqual(updated.track_input, "spotify:track:new")
        self.assertEqual(updated.caption, "new")

    def test_feed_shows_only_friends(self):
        viewer = User.objects.create_user(username="viewer", password="pw")
        friend = User.objects.create_user(username="friend", password="pw")
        stranger = User.objects.create_user(username="stranger", password="pw")

        Friendship.objects.create(from_user=viewer, to_user=friend, status="accepted")

        SongShare.objects.create(user=friend, track_input="spotify:track:friend")
        SongShare.objects.create(user=stranger, track_input="spotify:track:stranger")

        self.client.login(username="viewer", password="pw")
        response = self.client.get(reverse("feed"))
        self.assertEqual(response.status_code, 200)

        shares = response.context["shares"]
        self.assertEqual(len(shares), 1)
        self.assertEqual(shares[0]["share"].user.username, "friend")
