from django.contrib import admin

from .models import Follow, FriendRequest, Like, Message, Notification, Post, Profile, Story


admin.site.register([Follow, FriendRequest, Like, Message, Notification, Post, Profile, Story])
