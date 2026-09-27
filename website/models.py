from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('PARENT', 'Parent'),
        ('CAREGIVER', 'Caregiver'),
        ('ADMINISTRATOR', 'Administrator'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    email = models.EmailField()
    phone_number = models.CharField(max_length=20, null=True, blank=True)
    address = models.TextField(null=True, blank=True)
    
    # Administrator-specific fields
    admin_title = models.CharField(max_length=100, null=True, blank=True, 
                                 help_text="Optional: Your position or title")
    admin_department = models.CharField(max_length=100, null=True, blank=True,
                                     help_text="Optional: Your department")
    
    def __str__(self):
        return f"{self.user.username} - {self.role}"
    
    def clean(self):
        if self.role in ['PARENT', 'CAREGIVER']:
            if not self.phone_number:
                raise ValidationError({'phone_number': 'Phone number is required for parents and caregivers.'})
            if not self.address:
                raise ValidationError({'address': 'Address is required for parents and caregivers.'})
        
        if self.role == 'ADMINISTRATOR' and not self._state.adding:
            self.user.is_staff = True
            self.user.save(update_fields=['is_staff'])

    def save(self, *args, **kwargs):
        if not self._state.adding:  # Only validate for updates, not creation
            self.full_clean()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created and not hasattr(instance, 'userprofile'):
        role = 'ADMINISTRATOR' if instance.is_staff or instance.is_superuser else 'PARENT'
        UserProfile.objects.create(user=instance, role=role)

class LearningSession(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.start_time}"

class Interaction(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    timestamp = models.DateTimeField(auto_now_add=True)
    action = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.user.username} - {self.action} - {self.timestamp}"

class LLMSettings(models.Model):
    BACKEND_CHOICES = [
        ('anthropic', 'Anthropic'),
        ('ollama', 'Ollama'),
        ('lmstudio', 'LM Studio'),
        ('vllm', 'vLLM'),
        ('llamacpp', 'llama.cpp'),
    ]

    backend = models.CharField(max_length=20, choices=BACKEND_CHOICES, default='anthropic')
    anthropic_api_key = models.CharField(max_length=255, blank=True, default='')
    ollama_base_url = models.CharField(max_length=255, default='http://ollama:12434')
    ollama_model = models.CharField(max_length=100, default='llama3.2:1b')
    local_api_url = models.CharField(
        max_length=255, blank=True, default='',
        help_text='Base URL for LM Studio / vLLM / llama.cpp (OpenAI-compatible)',
    )
    local_model = models.CharField(
        max_length=100, blank=True, default='',
        help_text='Model name for the local backend',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'LLM Settings'
        verbose_name_plural = 'LLM Settings'

    def __str__(self):
        return f"LLM Settings — {self.backend}"

    @classmethod
    def get_settings(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Document(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Document'
        verbose_name_plural = 'Documents'

        