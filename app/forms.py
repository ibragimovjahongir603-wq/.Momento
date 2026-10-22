from datetime import date

from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError

from .models import Comment, Message, Post, Profile, Story

MAX_VIDEO_SIZE = 50 * 1024 * 1024


class ImageOrVideoFormMixin:
    def clean(self):
        cleaned_data = super().clean()
        image_uploaded = bool(self.files.get(self.add_prefix('image')))
        video_uploaded = self.files.get(self.add_prefix('video'))

        if image_uploaded and video_uploaded:
            self.add_error('video', 'Bir vaqtda faqat rasm yoki video tanlang.')
        elif video_uploaded:
            cleaned_data['image'] = None
        elif image_uploaded:
            cleaned_data['video'] = None

        image = cleaned_data.get('image')
        video = cleaned_data.get('video')
        if not image and not video:
            self.add_error('image', 'Post yoki hikoya uchun rasm yoki video tanlang.')
        if video_uploaded and video_uploaded.size > MAX_VIDEO_SIZE:
            self.add_error('video', 'Video hajmi 50 MB dan oshmasligi kerak.')

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.files.get(self.add_prefix('video')):
            instance.image = None
        elif self.files.get(self.add_prefix('image')):
            instance.video = None

        if commit:
            instance.save()
            self.save_m2m()
        return instance


class SignupForm(UserCreationForm):
    birth_year = forms.IntegerField(
        label='Tug‘ilgan yil',
        min_value=1900,
        max_value=date.today().year - 13,
        widget=forms.NumberInput(attrs={
            'placeholder': '2005',
            'inputmode': 'numeric',
            'autocomplete': 'bday-year',
        }),
        help_text='Kamida 13 yoshda ekaningizni tasdiqlash uchun.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'birth_year', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['username'].widget.attrs.update({
            'placeholder': 'Masalan, laylo',
            'autocomplete': 'username',
        })
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'


class ProfileForm(forms.ModelForm):
    class Meta:
        model = Profile
        fields = ['avatar']
        widgets = {
            'avatar': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
        }


class PostForm(ImageOrVideoFormMixin, forms.ModelForm):
    class Meta:
        model = Post
        fields = ['image', 'video', 'caption']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'video': forms.ClearableFileInput(attrs={
                'accept': 'video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov',
            }),
            'caption': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Surat haqida yozing...',
                'maxlength': 500,
            }),
        }


class StoryForm(ImageOrVideoFormMixin, forms.ModelForm):
    class Meta:
        model = Story
        fields = ['image', 'video', 'caption']
        widgets = {
            'image': forms.ClearableFileInput(attrs={'accept': 'image/*'}),
            'video': forms.ClearableFileInput(attrs={
                'accept': 'video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov',
            }),
            'caption': forms.TextInput(attrs={
                'placeholder': 'Hikoyaga izoh qo‘shing...',
                'maxlength': 240,
            }),
        }


class CommentForm(forms.ModelForm):
    class Meta:
        model = Comment
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Komment yozing...',
                'maxlength': 500,
            }),
        }


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ['body']
        widgets = {
            'body': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Xabar yozing...',
                'maxlength': 2000,
            }),
        }