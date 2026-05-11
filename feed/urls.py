from django.urls import path

from . import views

urlpatterns = [
    path("", views.feed, name="feed"),
    path("page/", views.feed_page, name="feed_page"),
    path("search/", views.spotify_search, name="spotify_search"),
    path("reactions/<int:share_id>/", views.reactions, name="reactions"),
    path("react/<int:share_id>/", views.react, name="react"),
    path("replies/<int:share_id>/", views.replies, name="replies"),
    path("reply/<int:share_id>/", views.reply, name="reply"),
]
