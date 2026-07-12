from django.db import models

from .crypto import EncryptedImageField


def user_face_path(instance, filename):
    if hasattr(instance, 'username'):
        username = instance.username
    elif hasattr(instance, 'user') and hasattr(instance.user, 'username'):
        username = instance.user.username
    else:
        username = 'unknown'
    return f'face_images/{username}/{filename}'


class UserProfile(models.Model):
    username = models.CharField(max_length=20, unique=True)
    password = models.CharField(max_length=128)
    email = models.EmailField(max_length=50, unique=True)
    phone = models.CharField(max_length=50, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    face_image = EncryptedImageField(upload_to=user_face_path, blank=True, null=True)

    class Meta:
        db_table = 'face_user_profile'

    def __str__(self):
        return self.username


class UserFaceImage(models.Model):
    user = models.ForeignKey(UserProfile, related_name='face_images', on_delete=models.CASCADE)
    image = EncryptedImageField(upload_to=user_face_path)
    face_token = models.CharField(max_length=128, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'face_user_face_image'

    def __str__(self):
        return f"{self.user.username} face #{self.id}"
