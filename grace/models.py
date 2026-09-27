from django.db import models
from django.contrib.auth.models import User
from django.conf import settings

class Conversation(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='grace_conversations')
    created_at = models.DateTimeField(auto_now_add=True)
    title = models.CharField(max_length=200)
    
    def __str__(self):
        return f"{self.title} - {self.user.username}"

class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name='grace_messages')
    content = models.TextField()
    is_user = models.BooleanField(default=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['timestamp']


class SocialCurriculum(models.Model):
    AGE_RANGES = [
        ('0-1', '0-1 years'),
        ('1-2', '1-2 years'),
        ('2-3', '2-3 years'),
        ('3-4', '3-4 years'),
        ('4-5', '4-5 years'),
    ]

    ACTIVITY_TYPES = [
        ('EMOTIONAL', 'Emotional Awareness'),
        ('SHARING', 'Sharing & Turn-Taking'),
        ('EMPATHY', 'Empathy Building'),
        ('CONFLICT', 'Conflict Resolution'),
        ('SELF_REG', 'Self-Regulation'),
        ('SOCIAL_PLAY', 'Social Play'),
        ('COMMUNICATION', 'Communication Skills'),
    ]

    title = models.CharField(max_length=200, default='')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES, default='SOCIAL_PLAY')
    age_range = models.CharField(max_length=10, choices=AGE_RANGES, default='2-3')
    description = models.TextField(help_text="Step-by-step description of the activity", default='')
    developmental_goal = models.TextField(help_text="What social-emotional skill this activity develops", default='')
    materials = models.TextField(blank=True, default='')
    duration_minutes = models.PositiveIntegerField(default=15)
    group_size = models.CharField(max_length=50, blank=True, default='', help_text="e.g. 2-4 children, individual, whole class")
    author = models.CharField(max_length=100, blank=True, default='')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Social Curriculum Activities'

    def __str__(self):
        return f"{self.title} ({self.get_activity_type_display()}, {self.age_range})"
  