from django.contrib import admin

from .models import UserFaceImage, UserProfile


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ['id', 'username', 'created_at']
    search_fields = ['username']


@admin.register(UserFaceImage)
class UserFaceImageAdmin(admin.ModelAdmin):
    list_display = ['id', 'user', 'face_token', 'created_at']
