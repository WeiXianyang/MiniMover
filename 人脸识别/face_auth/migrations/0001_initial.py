# Generated manually

from django.db import migrations, models
import django.db.models.deletion
import face_auth.crypto


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name='UserProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username', models.CharField(max_length=20, unique=True)),
                ('password', models.CharField(max_length=128)),
                ('email', models.EmailField(max_length=50, unique=True)),
                ('phone', models.CharField(max_length=50, unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('face_image', face_auth.crypto.EncryptedImageField(blank=True, null=True, upload_to=face_auth.models.user_face_path)),
            ],
            options={'db_table': 'face_user_profile'},
        ),
        migrations.CreateModel(
            name='UserFaceImage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('image', face_auth.crypto.EncryptedImageField(upload_to=face_auth.models.user_face_path)),
                ('face_token', models.CharField(blank=True, max_length=128, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='face_images', to='face_auth.userprofile')),
            ],
            options={'db_table': 'face_user_face_image'},
        ),
    ]
