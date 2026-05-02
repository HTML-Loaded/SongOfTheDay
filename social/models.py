from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Friendship(models.Model):
    from_user = models.ForeignKey(User, related_name="sent_requests", on_delete=models.CASCADE)
    to_user = models.ForeignKey(User, related_name="received_requests", on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=[
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("blocked", "Blocked"),
    ])
    created_at = models.DateTimeField(auto_now_add=True)
