from rest_framework import serializers

from .crypto import aes_decrypt_text
from .models import UserFaceImage, UserProfile


class UserFaceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserFaceImage
        fields = ['id', 'face_token', 'created_at']


class UserSerializer(serializers.ModelSerializer):
    face_images = UserFaceImageSerializer(many=True, read_only=True)
    email = serializers.SerializerMethodField()
    phone = serializers.SerializerMethodField()

    class Meta:
        model = UserProfile
        fields = ['id', 'username', 'email', 'phone', 'created_at', 'face_images']

    def get_email(self, obj):
        try:
            return aes_decrypt_text(obj.email)
        except Exception:
            return obj.email

    def get_phone(self, obj):
        try:
            return aes_decrypt_text(obj.phone)
        except Exception:
            return obj.phone
