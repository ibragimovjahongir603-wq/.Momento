from datetime import timedelta
from io import BytesIO
from tempfile import TemporaryDirectory

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.files.storage import default_storage
from django.test import TestCase
from django.test import override_settings
from django.utils import timezone
from django.urls import reverse
from PIL import Image

from .models import (
	Comment, Follow, FriendRequest, Message, Notification, Post, Profile, Story, TypingStatus,
)


class AccountAndFeedTests(TestCase):
	def test_home_redirects_to_login_when_signed_out(self):
		response = self.client.get(reverse('home'))

		self.assertRedirects(response, f"{reverse('login')}?next={reverse('home')}")

	def test_signup_logs_user_in_and_opens_feed(self):
		response = self.client.post(reverse('signup'), {
			'username': 'aziza',
			'birth_year': '2005',
			'password1': 'StrongPass!2026',
			'password2': 'StrongPass!2026',
		})

		self.assertRedirects(response, reverse('home'))
		self.assertTrue(User.objects.filter(username='aziza').exists())
		self.assertIn('_auth_user_id', self.client.session)
		self.assertEqual(Profile.objects.get(user__username='aziza').birth_year, 2005)

	def test_signup_requires_at_least_age_thirteen(self):
		response = self.client.post(reverse('signup'), {
			'username': 'aziza',
			'birth_year': '2020',
			'password1': 'StrongPass!2026',
			'password2': 'StrongPass!2026',
		})

		self.assertEqual(response.status_code, 200)
		self.assertFalse(User.objects.filter(username='aziza').exists())
		self.assertContains(response, 'Tug‘ilgan yil')

	def test_login_shows_signup_link(self):
		response = self.client.get(reverse('login'))

		self.assertContains(response, reverse('signup'))

	def test_login_and_signup_do_not_offer_google_auth(self):
		for page in ('login', 'signup'):
			with self.subTest(page=page):
				response = self.client.get(reverse(page))
				self.assertNotContains(response, 'Google orqali')

	def test_profile_does_not_offer_google_auth(self):
		user = User.objects.create_user(username='aziza', password='StrongPass!2026')
		self.client.force_login(user)

		response = self.client.get(reverse('profile'))

		self.assertNotContains(response, 'Google orqali')

	def test_existing_user_can_log_in(self):
		User.objects.create_user(username='aziza', password='StrongPass!2026')

		response = self.client.post(reverse('login'), {
			'username': 'aziza',
			'password': 'StrongPass!2026',
		})

		self.assertRedirects(response, reverse('home'))
		self.assertEqual(self.client.get(reverse('home')).status_code, 200)

	def test_signed_in_user_can_publish_an_image(self):
		user = User.objects.create_user(username='aziza', password='StrongPass!2026')
		self.client.force_login(user)
		image_data = BytesIO()
		Image.new('RGB', (2, 2), color='green').save(image_data, format='PNG')
		image_data.seek(0)
		uploaded_image = SimpleUploadedFile('memory.png', image_data.read(), content_type='image/png')

		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(reverse('home'), {
					'image': uploaded_image,
					'caption': 'Birinchi kadr',
				})

		self.assertRedirects(response, reverse('home'))
		self.assertTrue(Post.objects.filter(author=user, caption='Birinchi kadr').exists())

	def test_signed_in_user_can_publish_and_play_a_video_post(self):
		user = User.objects.create_user(username='aziza', password='StrongPass!2026')
		self.client.force_login(user)
		video = SimpleUploadedFile('clip.mp4', b'test video bytes', content_type='video/mp4')

		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(reverse('home'), {
					'video': video,
					'caption': 'Video kadr',
				})

				self.assertRedirects(response, reverse('home'))
				post = Post.objects.get(author=user)
				self.assertTrue(post.video.name.endswith('clip.mp4'))
				self.assertFalse(post.image)
				self.assertContains(self.client.get(reverse('home')), '<video', html=False)

	def test_signed_in_user_can_add_a_comment_to_a_post(self):
		user = User.objects.create_user(username='aziza', password='StrongPass!2026')
		self.client.force_login(user)
		post = Post.objects.create(author=user, caption='Birinchi kadr')

		response = self.client.post(reverse('add_comment', args=[post.pk]), {
			'body': 'Chiroyli surat!',
			'next': f'{reverse("home")}#comments-{post.pk}',
		}, follow=True)

		self.assertTrue(Comment.objects.filter(post=post, author=user, body='Chiroyli surat!').exists())
		self.assertContains(response, 'Chiroyli surat!')
		self.assertEqual(response.redirect_chain[0][0], f'{reverse("home")}#comments-{post.pk}')

	def test_post_rejects_unsupported_video_extension(self):
		user = User.objects.create_user(username='aziza', password='StrongPass!2026')
		self.client.force_login(user)
		video = SimpleUploadedFile('clip.exe', b'not a video', content_type='video/mp4')

		response = self.client.post(reverse('home'), {'video': video})

		self.assertEqual(response.status_code, 200)
		self.assertFalse(Post.objects.filter(author=user).exists())

	def test_user_can_upload_profile_avatar(self):
		user = User.objects.create_user(username='aziza', password='StrongPass!2026')
		self.client.force_login(user)
		image_data = BytesIO()
		Image.new('RGB', (2, 2), color='coral').save(image_data, format='PNG')
		image_data.seek(0)
		uploaded_image = SimpleUploadedFile('avatar.png', image_data.read(), content_type='image/png')

		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(reverse('profile'), {'avatar': uploaded_image})

		self.assertRedirects(response, reverse('profile'))
		self.assertTrue(Profile.objects.get(user=user).avatar.name.startswith('avatars/'))

	def test_user_can_replace_profile_avatar(self):
		user = User.objects.create_user(username='aziza', password='StrongPass!2026')
		self.client.force_login(user)

		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				for filename, color in [('first.png', 'green'), ('second.png', 'blue')]:
					image_data = BytesIO()
					Image.new('RGB', (2, 2), color=color).save(image_data, format='PNG')
					image_data.seek(0)
					response = self.client.post(reverse('profile'), {
						'avatar': SimpleUploadedFile(filename, image_data.read(), content_type='image/png'),
					})
					self.assertRedirects(response, reverse('profile'))
				self.assertFalse(default_storage.exists('avatars/first.png'))
				self.assertTrue(default_storage.exists('avatars/second.png'))

		avatar = Profile.objects.get(user=user).avatar.name
		self.assertTrue(avatar.endswith('second.png'))


class SocialFeatureTests(TestCase):
	def setUp(self):
		self.user = User.objects.create_user(username='aziza', password='StrongPass!2026')
		self.other = User.objects.create_user(username='bekzod', password='StrongPass!2026')
		Profile.objects.create(user=self.user)
		Profile.objects.create(user=self.other)
		self.client.force_login(self.user)

	def test_post_comments_open_in_comment_dialog(self):
		post = Post.objects.create(author=self.other, caption='Yangi surat')
		for index in range(3):
			Comment.objects.create(post=post, author=self.user, body=f'Izoh {index}')

		response = self.client.get(reverse('home'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, f'data-comments-open="comments-dialog-{post.pk}"')
		self.assertContains(response, f'id="comments-dialog-{post.pk}"')
		self.assertContains(response, 'Izoh yozing')
		self.assertContains(response, 'Yuborish')
		self.assertNotContains(response, 'comments-post-caption')
		self.assertNotContains(response, 'comment-avatar-current')
		self.assertContains(response, 'Izoh 2')

	def test_search_finds_people_by_username(self):
		response = self.client.get(reverse('search'), {'q': 'bek'})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'bekzod')
		self.assertContains(response, reverse('public_profile', args=['bekzod']))

	def test_search_page_lists_other_accounts_without_a_query(self):
		response = self.client.get(reverse('search'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'bekzod')
		self.assertContains(response, reverse('public_profile', args=['bekzod']))
		self.assertNotContains(response, reverse('public_profile', args=['aziza']))

	def test_search_lists_all_matching_accounts_without_cutoff(self):
		for index in range(35):
			User.objects.create_user(username=f'user{index:02d}', password='StrongPass!2026')

		response = self.client.get(reverse('search'), {'q': 'user'})

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'user00')
		self.assertContains(response, 'user34')
		self.assertEqual(len(response.context['results']), 35)

	def test_search_creates_missing_profile_for_older_accounts(self):
		self.other.profile.delete()

		response = self.client.get(reverse('search'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'bekzod')
		self.assertTrue(Profile.objects.filter(user=self.other).exists())

	def test_personal_profile_is_visible_from_search_results(self):
		post = Post.objects.create(author=self.other, caption='Profil izohi')
		Comment.objects.create(post=post, author=self.user, body='Profilga izoh')

		response = self.client.get(reverse('public_profile', args=['bekzod']))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'bekzod')
		self.assertContains(response, f'data-comments-open="comments-dialog-{post.pk}"')
		self.assertContains(response, f'id="comments-dialog-{post.pk}"')
		self.assertContains(response, reverse('followers', args=['bekzod']))
		self.assertContains(response, reverse('following', args=['bekzod']))

	def test_profile_shows_instagram_style_counts_and_own_posts(self):
		Post.objects.create(author=self.user, caption='Profil postim')
		Follow.objects.create(follower=self.other, followed=self.user)
		response = self.client.get(reverse('profile'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, reverse('followers', args=['aziza']))
		self.assertContains(response, reverse('following', args=['aziza']))
		self.assertContains(response, 'Profil postim')
		self.assertContains(response, 'class="profile-post-tile"', html=False)

	def test_follow_lists_show_the_correct_users(self):
		following_user = User.objects.create_user(username='dilnoza', password='StrongPass!2026')
		Follow.objects.create(follower=self.other, followed=self.user)
		Follow.objects.create(follower=self.user, followed=following_user)

		followers_response = self.client.get(reverse('followers', args=['aziza']))
		following_response = self.client.get(reverse('following', args=['aziza']))

		self.assertEqual(followers_response.status_code, 200)
		self.assertContains(followers_response, 'bekzod')
		self.assertNotContains(followers_response, 'dilnoza')
		self.assertEqual(following_response.status_code, 200)
		self.assertContains(following_response, 'dilnoza')
		self.assertNotContains(following_response, 'bekzod')

	def test_follow_can_be_added_and_removed(self):
		url = reverse('follow_toggle', args=['bekzod'])

		self.client.post(url)
		self.assertTrue(Follow.objects.filter(follower=self.user, followed=self.other).exists())
		self.assertTrue(Notification.objects.filter(
			recipient=self.other, actor=self.user, kind=Notification.FOLLOW,
		).exists())
		self.client.post(url)
		self.assertFalse(Follow.objects.filter(follower=self.user, followed=self.other).exists())

	def test_friend_request_enables_private_messages(self):
		self.client.post(reverse('friend_action', args=['bekzod', 'send']))
		friend_request = FriendRequest.objects.get(from_user=self.user, to_user=self.other)
		self.assertEqual(friend_request.status, FriendRequest.PENDING)

		self.client.force_login(self.other)
		self.client.post(reverse('friend_action', args=['aziza', 'accept']))
		friend_request.refresh_from_db()
		self.assertEqual(friend_request.status, FriendRequest.ACCEPTED)
		response = self.client.post(reverse('conversation', args=['aziza']), {'body': 'Salom!'})

		self.assertRedirects(response, reverse('conversation', args=['aziza']))
		self.assertTrue(Message.objects.filter(sender=self.other, receiver=self.user, body='Salom!').exists())
		self.assertTrue(Notification.objects.filter(
			recipient=self.user, actor=self.other, kind=Notification.MESSAGE,
		).exists())

	def test_inbox_lists_friends_and_filters_conversations(self):
		FriendRequest.objects.create(from_user=self.user, to_user=self.other, status=FriendRequest.ACCEPTED)
		response = self.client.get(reverse('inbox'))

		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'bekzod')
		self.assertContains(response, reverse('conversation', args=['bekzod']))

		response = self.client.get(reverse('inbox'), {'q': 'nobody'})
		self.assertEqual(response.status_code, 200)
		self.assertNotContains(response, 'bekzod')
		self.assertContains(response, 'Suhbat topilmadi')

	def test_non_friends_cannot_open_a_conversation(self):
		response = self.client.get(reverse('conversation', args=['bekzod']))

		self.assertRedirects(response, reverse('search'))
		self.assertFalse(Message.objects.exists())

	def test_conversation_shows_online_status_from_recent_activity(self):
		FriendRequest.objects.create(from_user=self.user, to_user=self.other, status=FriendRequest.ACCEPTED)
		self.other.profile.last_seen = timezone.now()
		self.other.profile.save(update_fields=['last_seen'])

		response = self.client.get(reverse('conversation', args=['bekzod']))
		self.assertEqual(response.status_code, 200)
		self.assertContains(response, 'Onlayn')

		self.other.profile.last_seen = timezone.now() - timedelta(minutes=10)
		self.other.profile.save(update_fields=['last_seen'])
		response = self.client.get(reverse('conversation', args=['bekzod']))
		self.assertContains(response, 'Oflayn')

	def test_conversation_presence_reports_online_and_remote_typing(self):
		FriendRequest.objects.create(from_user=self.user, to_user=self.other, status=FriendRequest.ACCEPTED)
		presence_url = reverse('conversation_presence', args=['bekzod'])

		response = self.client.get(presence_url)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json(), {'is_online': True, 'is_typing': False})

		response = self.client.post(
			presence_url,
			data='{"is_typing": true}',
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 200)
		self.assertTrue(TypingStatus.objects.filter(sender=self.user, recipient=self.other).exists())

		other_client = self.client_class()
		other_client.force_login(self.other)
		response = other_client.get(reverse('conversation_presence', args=['aziza']))
		self.assertEqual(response.json(), {'is_online': True, 'is_typing': True})

		response = self.client.post(
			presence_url,
			data='{"is_typing": false}',
			content_type='application/json',
		)
		self.assertEqual(response.status_code, 200)
		self.assertFalse(TypingStatus.objects.exists())

	def test_conversation_presence_is_limited_to_friends_and_valid_payloads(self):
		presence_url = reverse('conversation_presence', args=['bekzod'])
		self.assertEqual(self.client.get(presence_url).status_code, 403)

		FriendRequest.objects.create(from_user=self.user, to_user=self.other, status=FriendRequest.ACCEPTED)
		response = self.client.post(presence_url, data='{}', content_type='application/json')
		self.assertEqual(response.status_code, 400)

	def test_post_can_be_liked_unliked_and_edited_only_by_owner(self):
		post = Post.objects.create(author=self.other, image='posts/test.png', caption='Old')
		like_url = reverse('toggle_like', args=[post.pk])
		self.client.post(like_url)
		self.assertEqual(post.likes.count(), 1)
		self.client.post(like_url)
		self.assertEqual(post.likes.count(), 0)
		self.assertEqual(Notification.objects.filter(
			recipient=self.other, actor=self.user, kind=Notification.LIKE,
		).count(), 1)

		own_post = Post.objects.create(author=self.user, image='posts/own.png', caption='Old')
		response = self.client.post(reverse('edit_post', args=[own_post.pk]), {'caption': 'Updated'})
		own_post.refresh_from_db()
		self.assertRedirects(response, reverse('home'))
		self.assertEqual(own_post.caption, 'Updated')
		self.assertEqual(self.client.get(reverse('edit_post', args=[post.pk])).status_code, 404)

	def test_owner_can_delete_post(self):
		post = Post.objects.create(author=self.user, image='posts/own.png', caption='Remove')

		response = self.client.post(reverse('delete_post', args=[post.pk]))

		self.assertRedirects(response, reverse('home'))
		self.assertFalse(Post.objects.filter(pk=post.pk).exists())

	def test_notifications_are_listed_and_marked_read_with_ajax(self):
		post = Post.objects.create(author=self.user, caption='Bildirishnoma posti')
		Notification.objects.create(
			recipient=self.user, actor=self.other, kind=Notification.LIKE, post=post,
		)

		response = self.client.get(
			reverse('notification_feed'),
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)

		self.assertEqual(response.status_code, 200)
		self.assertContains(self.client.get(reverse('home')), 'Bildirishnomalar')
		self.assertEqual(response.json()['unread_count'], 1)
		self.assertEqual(response.json()['notifications'][0]['kind'], Notification.LIKE)
		self.assertEqual(
			response.json()['notifications'][0]['url'],
			f'{reverse("home")}#comments-{post.pk}',
		)

		response = self.client.post(
			reverse('notification_mark_read', args=[Notification.objects.get().pk]),
			HTTP_X_REQUESTED_WITH='XMLHttpRequest',
		)

		self.assertEqual(response.status_code, 200)
		self.assertEqual(response.json()['unread_count'], 0)
		self.assertTrue(Notification.objects.get().is_read)

	def test_ajax_notification_actions_require_the_recipient(self):
		notification = Notification.objects.create(
			recipient=self.other, actor=self.user, kind=Notification.FOLLOW,
		)

		response = self.client.post(reverse('notification_mark_read', args=[notification.pk]))

		self.assertEqual(response.status_code, 200)
		notification.refresh_from_db()
		self.assertFalse(notification.is_read)

	def test_comment_on_another_users_post_creates_notification(self):
		post = Post.objects.create(author=self.other, caption='Bekzod posti')

		self.client.post(reverse('add_comment', args=[post.pk]), {'body': 'Yaxshi!'})

		self.assertTrue(Notification.objects.filter(
			recipient=self.other, actor=self.user, kind=Notification.COMMENT, post=post,
		).exists())

	def test_story_upload_is_visible_on_profile_for_24_hours(self):
		image_data = BytesIO()
		Image.new('RGB', (2, 2), color='purple').save(image_data, format='PNG')
		image_data.seek(0)
		upload = SimpleUploadedFile('story.png', image_data.read(), content_type='image/png')

		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(reverse('profile'), {
					'story_submit': '1',
					'image': upload,
					'caption': 'Bugungi hikoya',
				})
				self.assertRedirects(response, reverse('profile'))
				story = Story.objects.get(author=self.user)
				self.assertContains(self.client.get(reverse('profile')), 'Bugungi hikoya')
				self.client.force_login(self.other)
				self.assertContains(
					self.client.get(reverse('public_profile', args=['aziza'])),
					'Bugungi hikoya',
				)
				story.expires_at = timezone.now() - timedelta(minutes=1)
				story.save(update_fields=['expires_at'])
				self.assertNotContains(
					self.client.get(reverse('public_profile', args=['aziza'])),
					'Bugungi hikoya',
				)

	def test_story_can_be_uploaded_as_a_video_and_played(self):
		video = SimpleUploadedFile('story.mp4', b'test video bytes', content_type='video/mp4')

		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(reverse('profile'), {
					'story_submit': '1',
					'video': video,
					'caption': 'Video hikoya',
				})

				self.assertRedirects(response, reverse('profile'))
				story = Story.objects.get(author=self.user)
				self.assertTrue(story.video.name.endswith('story.mp4'))
				self.assertFalse(story.image)
				self.assertContains(self.client.get(reverse('profile')), '<video', html=False)

	def test_post_can_be_changed_from_image_to_video(self):
		post = Post.objects.create(author=self.user, image='posts/old.png', caption='Old')
		video = SimpleUploadedFile('replacement.webm', b'test video bytes', content_type='video/webm')

		with TemporaryDirectory() as media_root:
			with override_settings(MEDIA_ROOT=media_root):
				response = self.client.post(reverse('edit_post', args=[post.pk]), {
					'video': video,
					'caption': 'Video post',
				})

		self.assertRedirects(response, reverse('home'))
		post.refresh_from_db()
		self.assertTrue(post.video.name.endswith('replacement.webm'))
		self.assertFalse(post.image)
