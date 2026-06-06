# Generated migration for ChatMessage model

from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('aiapp', '0007_quiz_upload_code'),
    ]

    operations = [
        migrations.CreateModel(
            name='ChatMessage',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('session_id', models.CharField(db_index=True, default='', help_text='Browser session identifier for tracking guest conversations', max_length=255)),
                ('role', models.CharField(choices=[('user', 'User'), ('model', 'AI Model')], db_index=True, help_text="Who sent the message: 'user' or 'model'", max_length=50)),
                ('text', models.TextField(help_text='The full text content of the message (can include markdown)')),
                ('language_code', models.CharField(default='en', help_text="Language code for the message (e.g., 'en', 'sw', 'ha')", max_length=10)),
                ('created_at', models.DateTimeField(auto_now_add=True, db_index=True, help_text='When the message was created')),
                ('user', models.ForeignKey(blank=True, db_index=True, help_text='The user who sent the message (null for anonymous/guest sessions)', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='chat_messages', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'ordering': ['created_at'],
            },
        ),
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(fields=['user', 'created_at'], name='aiapp_chatme_user_id_create_idx'),
        ),
        migrations.AddIndex(
            model_name='chatmessage',
            index=models.Index(fields=['session_id', 'created_at'], name='aiapp_chatme_session_create_idx'),
        ),
    ]
