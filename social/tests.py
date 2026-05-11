from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from accounts.models import Profile
from feed.models import SongShare

from .models import Friendship


class FriendsListTests(TestCase):
    def test_requires_login(self):
        response = self.client.get(reverse("friends_list"))
        self.assertEqual(response.status_code, 302)

    def test_lists_only_accepted_friends(self):
        alice = User.objects.create_user(username="alice", password="pw")
        bob = User.objects.create_user(username="bob", password="pw")
        chris = User.objects.create_user(username="chris", password="pw")

        Friendship.objects.create(from_user=alice, to_user=bob, status="accepted")
        Friendship.objects.create(from_user=alice, to_user=chris, status="pending")

        self.client.login(username="alice", password="pw")
        response = self.client.get(reverse("friends_list"))

        self.assertEqual(response.status_code, 200)
        self.assertIn(bob, response.context["friends"])
        self.assertNotIn(chris, response.context["friends"])

    def test_send_accept_and_cancel_requests(self):
        alice = User.objects.create_user(username="alice", password="pw")
        bob = User.objects.create_user(username="bob", password="pw")

        self.client.login(username="alice", password="pw")
        response = self.client.post(
            reverse("send_friend_request"),
            {"username": "bob"},
            follow=True,
        )
        self.assertEqual(response.status_code, 200)

        friendship = Friendship.objects.get(from_user=alice, to_user=bob)
        self.assertEqual(friendship.status, "pending")

        self.client.logout()
        self.client.login(username="bob", password="pw")
        response = self.client.post(
            reverse("accept_friend_request", args=[friendship.id]),
            follow=True,
        )
        self.assertEqual(response.status_code, 200)
        friendship.refresh_from_db()
        self.assertEqual(friendship.status, "accepted")

        response = self.client.get(reverse("friends_list"))
        self.assertContains(response, "alice")

        self.client.logout()
        self.client.login(username="alice", password="pw")
        response = self.client.get(reverse("friends_list"))
        self.assertContains(response, "bob")

        chris = User.objects.create_user(username="chris", password="pw")
        self.client.post(reverse("send_friend_request"), {"username": "chris"})
        pending = Friendship.objects.get(from_user=alice, to_user=chris)
        self.client.post(reverse("cancel_friend_request", args=[pending.id]))
        self.assertFalse(Friendship.objects.filter(id=pending.id).exists())

    def test_decline_request(self):
        alice = User.objects.create_user(username="alice", password="pw")
        bob = User.objects.create_user(username="bob", password="pw")

        friendship = Friendship.objects.create(from_user=alice, to_user=bob, status="pending")
        self.client.login(username="bob", password="pw")
        self.client.post(reverse("decline_friend_request", args=[friendship.id]))

        self.assertFalse(Friendship.objects.filter(id=friendship.id).exists())


class FriendProfileTests(TestCase):
    def test_requires_friendship(self):
        alice = User.objects.create_user(username="alice", password="pw")
        bob = User.objects.create_user(username="bob", password="pw")
        self.client.login(username="alice", password="pw")

        response = self.client.get(reverse("friend_profile", args=["bob"]))
        self.assertEqual(response.status_code, 404)

    def test_renders_friend_profile(self):
        alice = User.objects.create_user(username="alice", password="pw")
        bob = User.objects.create_user(username="bob", password="pw")
        Friendship.objects.create(from_user=alice, to_user=bob, status="accepted")

        profile = Profile.objects.get(user=bob)
        profile.bio = "hello there"
        profile.save(update_fields=["bio"])
        SongShare.objects.create(user=bob, track_input="spotify:track:123", caption="caption")

        self.client.login(username="alice", password="pw")
        response = self.client.get(reverse("friend_profile", args=["bob"]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "hello there")
        self.assertContains(response, "open.spotify.com/embed/track/123")

    def test_now_playing_endpoint_requires_friendship(self):
        alice = User.objects.create_user(username="alice", password="pw")
        bob = User.objects.create_user(username="bob", password="pw")
        self.client.login(username="alice", password="pw")
        response = self.client.get(reverse("friend_now_playing", args=["bob"]))
        self.assertEqual(response.status_code, 404)

    def test_friends_now_playing_requires_login(self):
        response = self.client.get(reverse("friends_now_playing"))
        self.assertEqual(response.status_code, 302)

    def test_friends_now_playing_lists_friends(self):
        alice = User.objects.create_user(username="alice", password="pw")
        bob = User.objects.create_user(username="bob", password="pw")
        Friendship.objects.create(from_user=alice, to_user=bob, status="accepted")

        self.client.login(username="alice", password="pw")
        response = self.client.get(reverse("friends_now_playing"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("bob", (response.json().get("now_playing") or {}))
