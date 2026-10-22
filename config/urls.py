"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from django.urls import path

from app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.home, name='home'),
    path('profile/', views.edit_profile, name='profile'),
    path('search/', views.search_users, name='search'),
    path('friends/', views.friends, name='friends'),
    path('messages/', views.inbox, name='inbox'),
    path('messages/<str:username>/', views.conversation, name='conversation'),
    path('messages/<str:username>/presence/', views.conversation_presence, name='conversation_presence'),
    path('users/<str:username>/followers/', views.follow_list, {'list_type': 'followers'}, name='followers'),
    path('users/<str:username>/following/', views.follow_list, {'list_type': 'following'}, name='following'),
    path('users/<str:username>/', views.public_profile, name='public_profile'),
    path('users/<str:username>/follow/', views.follow_toggle, name='follow_toggle'),
    path('users/<str:username>/friends/<str:action>/', views.friend_action, name='friend_action'),
    path('posts/<int:post_id>/comment/', views.add_comment, name='add_comment'),
    path('posts/<int:post_id>/like/', views.toggle_like, name='toggle_like'),
    path('posts/<int:post_id>/edit/', views.edit_post, name='edit_post'),
    path('posts/<int:post_id>/delete/', views.delete_post, name='delete_post'),
    path('signup/', views.signup, name='signup'),
    path('login/', auth_views.LoginView.as_view(template_name='app/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('heartbeat/', views.heartbeat, name='heartbeat'),
    path('notifications/', views.notification_feed, name='notification_feed'),
    path(
        'notifications/<int:notification_id>/read/',
        views.notification_mark_read,
        name='notification_mark_read',
    ),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
