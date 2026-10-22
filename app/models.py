from datetime import timedelta

from django.contrib.auth.models import User
from django.db import models
from django.core.validators import FileExtensionValidator
from django.utils import timezone


def default_story_expiration():
	return timezone.now() + timedelta(hours=24)


class Profile(models.Model):
	user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
	avatar = models.ImageField(upload_to='avatars/', blank=True)
	birth_year = models.PositiveSmallIntegerField(null=True, blank=True)
	last_seen = models.DateTimeField(default=timezone.now)

	def save(self, *args, **kwargs):
		update_fields = kwargs.get('update_fields')
		previous_avatar = None
		if self.pk and (update_fields is None or 'avatar' in update_fields):
			previous_avatar = type(self).objects.filter(pk=self.pk).values_list('avatar', flat=True).first()

		super().save(*args, **kwargs)

		if previous_avatar and previous_avatar != self.avatar.name:
			self.avatar.storage.delete(previous_avatar)

	def is_online(self, threshold_seconds=300):
		return (timezone.now() - self.last_seen).total_seconds() <= threshold_seconds

	def __str__(self):
		return f'{self.user.username} profile'


class Post(models.Model):
	author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='posts')
	image = models.ImageField(upload_to='posts/%Y/%m/', blank=True, null=True)
	video = models.FileField(
		upload_to='posts/%Y/%m/videos/',
		blank=True,
		null=True,
		validators=[FileExtensionValidator(allowed_extensions=['mp4', 'webm', 'mov'])],
	)
	caption = models.CharField(max_length=500, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.author.username}: {self.caption[:40]}'


class Follow(models.Model):
	follower = models.ForeignKey(User, on_delete=models.CASCADE, related_name='following')
	followed = models.ForeignKey(User, on_delete=models.CASCADE, related_name='followers')
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['follower', 'followed'], name='unique_follow'),
			models.CheckConstraint(condition=~models.Q(follower=models.F('followed')), name='no_self_follow'),
		]

	def __str__(self):
		return f'{self.follower.username} follows {self.followed.username}'


class FriendRequest(models.Model):
	PENDING = 'pending'
	ACCEPTED = 'accepted'
	STATUS_CHOICES = [(PENDING, 'Kutilmoqda'), (ACCEPTED, 'Qabul qilingan')]

	from_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_friend_requests')
	to_user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_friend_requests')
	status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=PENDING)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['from_user', 'to_user'], name='unique_friend_request'),
			models.CheckConstraint(condition=~models.Q(from_user=models.F('to_user')), name='no_self_friend_request'),
		]

	def __str__(self):
		return f'{self.from_user.username} → {self.to_user.username} ({self.status})'


class Like(models.Model):
	user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='post_likes')
	post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='likes')
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['user', 'post'], name='unique_post_like'),
		]

	def __str__(self):
		return f'{self.user.username} liked post {self.post_id}'


class Comment(models.Model):
	post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name='comments')
	author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='comments')
	body = models.TextField(max_length=500)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.author.username} commented on post {self.post_id}'


class Message(models.Model):
	sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
	receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
	body = models.TextField(max_length=2000)
	created_at = models.DateTimeField(auto_now_add=True)

	class Meta:
		ordering = ['created_at']
		constraints = [
			models.CheckConstraint(condition=~models.Q(sender=models.F('receiver')), name='no_self_message'),
		]

	def __str__(self):
		return f'{self.sender.username} → {self.receiver.username}'


class TypingStatus(models.Model):
	sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='typing_statuses')
	recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_typing_statuses')
	updated_at = models.DateTimeField(auto_now=True)

	class Meta:
		constraints = [
			models.UniqueConstraint(fields=['sender', 'recipient'], name='unique_typing_status'),
			models.CheckConstraint(condition=~models.Q(sender=models.F('recipient')), name='no_self_typing_status'),
		]

	def __str__(self):
		return f'{self.sender.username} typing to {self.recipient.username}'


class Notification(models.Model):
	LIKE = 'like'
	COMMENT = 'comment'
	FOLLOW = 'follow'
	MESSAGE = 'message'
	TYPE_CHOICES = [
		(LIKE, 'Yoqdi'),
		(COMMENT, 'Komment'),
		(FOLLOW, 'Obuna'),
		(MESSAGE, 'Xabar'),
	]

	recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
	actor = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_notifications')
	kind = models.CharField(max_length=10, choices=TYPE_CHOICES)
	post = models.ForeignKey(
		Post, on_delete=models.SET_NULL, null=True, blank=True, related_name='notifications',
	)
	created_at = models.DateTimeField(auto_now_add=True)
	is_read = models.BooleanField(default=False)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.actor.username} → {self.recipient.username} ({self.kind})'


class Story(models.Model):
	author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='stories')
	image = models.ImageField(upload_to='stories/%Y/%m/', blank=True, null=True)
	video = models.FileField(
		upload_to='stories/%Y/%m/videos/',
		blank=True,
		null=True,
		validators=[FileExtensionValidator(allowed_extensions=['mp4', 'webm', 'mov'])],
	)
	caption = models.CharField(max_length=240, blank=True)
	created_at = models.DateTimeField(auto_now_add=True)
	expires_at = models.DateTimeField(default=default_story_expiration)

	class Meta:
		ordering = ['-created_at']

	def __str__(self):
		return f'{self.author.username} story'
