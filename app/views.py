import json
from datetime import timedelta

from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.db.models import Count, Exists, OuterRef, Q, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme

from .forms import CommentForm, MessageForm, PostForm, ProfileForm, SignupForm, StoryForm
from .models import (
	Comment, Follow, FriendRequest, Like, Message, Notification, Post, Profile, Story, TypingStatus,
)


def signup(request):
	if request.user.is_authenticated:
		return redirect('home')

	form = SignupForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		user = form.save()
		Profile.objects.create(user=user, birth_year=form.cleaned_data['birth_year'])
		login(request, user)
		return redirect('home')

	return render(request, 'app/signup.html', {'form': form})


@login_required
def heartbeat(request):
	if request.method != 'POST':
		return JsonResponse({'status': 'invalid-method'}, status=405)
	Profile.objects.get_or_create(user=request.user)
	Profile.objects.filter(user=request.user).update(last_seen=timezone.now())
	return JsonResponse({'status': 'ok'})


@login_required
def notification_feed(request):
	if request.method != 'GET':
		return JsonResponse({'status': 'invalid-method'}, status=405)

	notifications = Notification.objects.filter(
		recipient=request.user,
	).select_related('actor', 'post')[:20]
	items = []
	for notification in notifications:
		if notification.kind in {Notification.LIKE, Notification.COMMENT}:
			url = reverse('home')
			if notification.post_id:
				url = f'{url}#comments-{notification.post_id}'
		elif notification.kind == Notification.FOLLOW:
			url = reverse('public_profile', args=[notification.actor.username])
		else:
			url = reverse('conversation', args=[notification.actor.username])
		items.append({
			'id': notification.pk,
			'actor': notification.actor.username,
			'kind': notification.kind,
			'created_at': timezone.localtime(notification.created_at).strftime('%d.%m %H:%M'),
			'is_read': notification.is_read,
			'url': url,
		})

	return JsonResponse({
		'notifications': items,
		'unread_count': Notification.objects.filter(recipient=request.user, is_read=False).count(),
	})


@login_required
def notification_mark_read(request, notification_id):
	if request.method != 'POST':
		return JsonResponse({'status': 'invalid-method'}, status=405)
	Notification.objects.filter(
		pk=notification_id, recipient=request.user, is_read=False,
	).update(is_read=True)
	return JsonResponse({
		'unread_count': Notification.objects.filter(recipient=request.user, is_read=False).count(),
	})


@login_required
def home(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	form = PostForm(request.POST or None, request.FILES or None)
	comment_form = CommentForm()
	if request.method == 'POST' and form.is_valid():
		post = form.save(commit=False)
		post.author = request.user
		post.save()
		return redirect('home')

	posts = Post.objects.select_related('author', 'author__profile').annotate(
		like_count=Count('likes', distinct=True),
		comment_count=Count('comments', distinct=True),
		is_liked=Exists(Like.objects.filter(
			post_id=OuterRef('pk'),
			user_id=request.user.pk,
		)),
	)
	return render(request, 'app/home.html', {
		'form': form,
		'comment_form': comment_form,
		'posts': posts,
		'profile': profile,
	})


@login_required
def edit_profile(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	form = ProfileForm(request.POST or None, request.FILES or None, instance=profile)
	story_form = StoryForm()
	if request.method == 'POST' and 'story_submit' in request.POST:
		story_form = StoryForm(request.POST, request.FILES)
		if story_form.is_valid():
			story = story_form.save(commit=False)
			story.author = request.user
			story.save()
			messages.success(request, 'Hikoyangiz 24 soatga joylandi.')
			return redirect('profile')
	elif request.method == 'POST' and form.is_valid():
		form.save()
		return redirect('profile')

	stories = Story.objects.filter(author=request.user, expires_at__gt=timezone.now())
	return render(request, 'app/profile.html', {
		'form': form,
		'profile': profile,
		'story_form': story_form,
		'stories': stories,
		'posts': Post.objects.filter(author=request.user),
	})


@login_required
def search_users(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	query = request.GET.get('q', '').strip()
	if query:
		users = User.objects.filter(
			Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query),
		).exclude(pk=request.user.pk).order_by('username')
	else:
		users = User.objects.exclude(pk=request.user.pk).order_by('-date_joined', 'username')
	for person in users:
		Profile.objects.get_or_create(user=person)
	return render(request, 'app/search.html', {
		'profile': profile,
		'query': query,
		'results': users,
	})


@login_required
def public_profile(request, username):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	person = get_object_or_404(User, username=username)
	if person == request.user:
		return redirect('profile')
	Profile.objects.get_or_create(user=person)
	posts = Post.objects.filter(author=person).select_related('author').annotate(
		like_count=Count('likes', distinct=True),
		comment_count=Count('comments', distinct=True),
		is_liked=Exists(Like.objects.filter(
			post_id=OuterRef('pk'),
			user_id=request.user.pk,
		)),
	)
	friend_request = FriendRequest.objects.filter(
		Q(from_user=request.user, to_user=person) | Q(from_user=person, to_user=request.user),
	).first()
	is_following = Follow.objects.filter(follower=request.user, followed=person).exists()
	is_followed_by = Follow.objects.filter(follower=person, followed=request.user).exists()
	mutual_follow = is_following and is_followed_by
	return render(request, 'app/public_profile.html', {
		'profile': profile,
		'person': person,
		'posts': posts,
		'comment_form': CommentForm(),
		'stories': Story.objects.filter(author=person, expires_at__gt=timezone.now()),
		'is_following': is_following,
		'is_followed_by': is_followed_by,
		'mutual_follow': mutual_follow,
		'friend_request': friend_request,
	})


@login_required
def follow_list(request, username, list_type):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	person = get_object_or_404(User, username=username)
	Profile.objects.get_or_create(user=person)

	if list_type == 'followers':
		people = User.objects.filter(following__followed=person)
		title = 'Obunachilar'
		empty_message = 'Hozircha obunachilar yo‘q.'
	else:
		people = User.objects.filter(followers__follower=person)
		title = 'Obunalar'
		empty_message = 'Hozircha obuna bo‘linganlar yo‘q.'

	people = people.exclude(pk=person.pk).distinct().order_by('username')
	for followed_user in people:
		Profile.objects.get_or_create(user=followed_user)

	return render(request, 'app/follow_list.html', {
		'profile': profile,
		'person': person,
		'people': people,
		'title': title,
		'empty_message': empty_message,
	})


@login_required
def follow_toggle(request, username):
	if request.method != 'POST':
		return redirect('search')
	person = get_object_or_404(User, username=username)
	if person != request.user:
		follow, created = Follow.objects.get_or_create(follower=request.user, followed=person)
		if not created:
			follow.delete()
		else:
			Notification.objects.create(
				recipient=person, actor=request.user, kind=Notification.FOLLOW,
			)
	return redirect('public_profile', username=person.username)


@login_required
def friend_action(request, username, action):
	if request.method != 'POST':
		return redirect('search')
	person = get_object_or_404(User, username=username)
	if person == request.user:
		return redirect('profile')
	if action == 'send':
		existing = FriendRequest.objects.filter(
			Q(from_user=request.user, to_user=person) | Q(from_user=person, to_user=request.user),
		).first()
		if existing is None:
			FriendRequest.objects.create(from_user=request.user, to_user=person)
		elif existing.from_user == person and existing.status == FriendRequest.PENDING:
			existing.status = FriendRequest.ACCEPTED
			existing.save(update_fields=['status'])
	elif action == 'accept':
		FriendRequest.objects.filter(
			from_user=person, to_user=request.user, status=FriendRequest.PENDING,
		).update(status=FriendRequest.ACCEPTED)
	elif action == 'reject':
		FriendRequest.objects.filter(
			from_user=person, to_user=request.user, status=FriendRequest.PENDING,
		).delete()
	return redirect('public_profile', username=person.username)


@login_required
def friends(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	incoming = FriendRequest.objects.filter(
		to_user=request.user, status=FriendRequest.PENDING,
	).select_related('from_user')
	for item in incoming:
		Profile.objects.get_or_create(user=item.from_user)
	accepted = FriendRequest.objects.filter(
		Q(from_user=request.user) | Q(to_user=request.user),
		status=FriendRequest.ACCEPTED,
	).select_related('from_user', 'to_user')
	friend_ids = [
		item.to_user_id if item.from_user_id == request.user.pk else item.from_user_id
		for item in accepted
	]
	friend_users = User.objects.filter(pk__in=friend_ids).order_by('username')
	for person in friend_users:
		Profile.objects.get_or_create(user=person)
	followers = User.objects.filter(
		following__followed=request.user,
	).exclude(pk=request.user.pk).distinct().order_by('username')
	following = User.objects.filter(
		followers__follower=request.user,
	).exclude(pk=request.user.pk).distinct().order_by('username')
	for person in list(followers) + list(following):
		Profile.objects.get_or_create(user=person)
	return render(request, 'app/friends.html', {
		'profile': profile,
		'incoming': incoming,
		'friend_users': friend_users,
		'followers': followers,
		'following': following,
	})


@login_required
def inbox(request):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	accepted = FriendRequest.objects.filter(
		Q(from_user=request.user) | Q(to_user=request.user),
		status=FriendRequest.ACCEPTED,
	)
	friend_ids = [
		item.to_user_id if item.from_user_id == request.user.pk else item.from_user_id
		for item in accepted
	]
	query = request.GET.get('q', '').strip()
	friend_users = User.objects.filter(pk__in=friend_ids)
	if query:
		friend_users = friend_users.filter(
			Q(username__icontains=query) | Q(first_name__icontains=query) | Q(last_name__icontains=query),
		)
	last_message = Message.objects.filter(
		Q(sender=OuterRef('pk'), receiver=request.user)
		| Q(sender=request.user, receiver=OuterRef('pk')),
	).order_by('-created_at')
	friend_users = friend_users.annotate(
		last_message_body=Subquery(last_message.values('body')[:1]),
		last_message_time=Subquery(last_message.values('created_at')[:1]),
	).order_by('-last_message_time', 'username')
	for person in friend_users:
		Profile.objects.get_or_create(user=person)
	return render(request, 'app/inbox.html', {
		'profile': profile,
		'friends': friend_users,
		'query': query,
	})


def _are_friends(first, second):
	return FriendRequest.objects.filter(
		Q(from_user=first, to_user=second) | Q(from_user=second, to_user=first),
		status=FriendRequest.ACCEPTED,
	).exists()


@login_required
def conversation(request, username):
	profile, _ = Profile.objects.get_or_create(user=request.user)
	person = get_object_or_404(User, username=username)
	Profile.objects.get_or_create(user=person)
	if person == request.user or not _are_friends(request.user, person):
		messages.error(request, 'Xabar yozish uchun avval do‘st bo‘lishingiz kerak.')
		return redirect('search')
	form = MessageForm(request.POST or None)
	if request.method == 'POST' and form.is_valid():
		message = form.save(commit=False)
		message.sender = request.user
		message.receiver = person
		message.save()
		Notification.objects.create(
			recipient=person, actor=request.user, kind=Notification.MESSAGE,
		)
		return redirect('conversation', username=person.username)
	conversation_messages = Message.objects.filter(
		Q(sender=request.user, receiver=person) | Q(sender=person, receiver=request.user),
	).select_related('sender', 'receiver')
	person_online = person.profile.is_online()
	return render(request, 'app/conversation.html', {
		'profile': profile,
		'person': person,
		'form': form,
		'conversation_messages': conversation_messages,
		'person_online': person_online,
	})


@login_required
def conversation_presence(request, username):
	if request.method not in {'GET', 'POST'}:
		return JsonResponse({'status': 'invalid-method'}, status=405)

	person = get_object_or_404(User, username=username)
	if person == request.user or not _are_friends(request.user, person):
		return JsonResponse({'status': 'forbidden'}, status=403)

	if request.method == 'POST':
		try:
			data = json.loads(request.body)
		except (json.JSONDecodeError, UnicodeDecodeError):
			return JsonResponse({'status': 'invalid-json'}, status=400)
		if not isinstance(data, dict) or not isinstance(data.get('is_typing'), bool):
			return JsonResponse({'status': 'invalid-data'}, status=400)
		if data['is_typing']:
			TypingStatus.objects.update_or_create(
				sender=request.user,
				recipient=person,
			)
		else:
			TypingStatus.objects.filter(sender=request.user, recipient=person).delete()

	is_typing = TypingStatus.objects.filter(
		sender=person,
		recipient=request.user,
		updated_at__gte=timezone.now() - timedelta(seconds=5),
	).exists()
	return JsonResponse({
		'is_online': person.profile.is_online(),
		'is_typing': is_typing,
	})


@login_required
def add_comment(request, post_id):
	if request.method != 'POST':
		return redirect('home')
	post = get_object_or_404(Post, pk=post_id)
	form = CommentForm(request.POST)
	if form.is_valid():
		comment = form.save(commit=False)
		comment.post = post
		comment.author = request.user
		comment.save()
		if post.author_id != request.user.pk:
			Notification.objects.create(
				recipient=post.author, actor=request.user, kind=Notification.COMMENT, post=post,
			)
	else:
		messages.error(request, 'Kommentni to‘g‘ri kiriting.')
	return_url = request.POST.get('next', '')
	if return_url and url_has_allowed_host_and_scheme(
		return_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
	):
		return redirect(return_url)
	return redirect('home')


@login_required
def toggle_like(request, post_id):
	if request.method == 'POST':
		post = get_object_or_404(Post, pk=post_id)
		like, created = post.likes.get_or_create(user=request.user)
		if not created:
			like.delete()
		elif post.author_id != request.user.pk:
			Notification.objects.create(
				recipient=post.author, actor=request.user, kind=Notification.LIKE, post=post,
			)
		return_url = request.POST.get('next', '')
		if return_url and url_has_allowed_host_and_scheme(
			return_url, allowed_hosts={request.get_host()}, require_https=request.is_secure(),
		):
			return redirect(return_url)
	return redirect('home')


@login_required
def edit_post(request, post_id):
	post = get_object_or_404(Post, pk=post_id, author=request.user)
	profile, _ = Profile.objects.get_or_create(user=request.user)
	form = PostForm(request.POST or None, request.FILES or None, instance=post)
	if request.method == 'POST' and form.is_valid():
		form.save()
		messages.success(request, 'Postingiz yangilandi.')
		return redirect('home')
	return render(request, 'app/edit_post.html', {'profile': profile, 'form': form, 'post': post})


@login_required
def delete_post(request, post_id):
	if request.method == 'POST':
		post = get_object_or_404(Post, pk=post_id, author=request.user)
		post.delete()
		messages.success(request, 'Postingiz o‘chirildi.')
	return redirect('home')
