from django.db import models
from django.contrib.auth import get_user_model

# Create your models here.
class MotorCurriculum(models.Model):
    ACTIVITY_TYPES = [
        ('FINE', 'Fine Motor'),
        ('GROSS', 'Gross Motor'),
        ('HAND_EYE', 'Hand-Eye Coordination'),
        ('BALANCE', 'Balance & Coordination'),
        ('SENSORY', 'Sensory Motor'),
    ]

    AGE_RANGES = [
        ('0-1', '0-1 years'),
        ('1-2', '1-2 years'),
        ('2-3', '2-3 years'),
        ('3-4', '3-4 years'),
        ('4-5', '4-5 years'),
    ]

    title = models.CharField(max_length=200, default='')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES, default='GROSS')
    age_range = models.CharField(max_length=10, choices=AGE_RANGES, default='2-3')
    description = models.TextField(help_text="Step-by-step description of the activity", default='')
    developmental_goal = models.TextField(help_text="What motor skill this activity develops", default='')
    materials = models.TextField(blank=True, default='')
    safety_notes = models.TextField(blank=True, default='')
    duration_minutes = models.PositiveIntegerField(default=15)
    activity_picture = models.ImageField(upload_to='motor_activity_pics/', blank=True, null=True)
    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Motor Curriculum Activities'

    def __str__(self):
        return f"{self.title} ({self.get_activity_type_display()}, {self.age_range})"

class PhysicalActivity(models.Model):
    ACTIVITY_TYPES = [
        ('FINE', 'Fine Motor'),
        ('GROSS', 'Gross Motor'),
        ('HAND_EYE', 'Hand-Eye Coordination'),
        ('DANCE', 'Dance & Movement'),
        ('SPORTS', 'Early Sports')
    ]
    
    AGE_RANGES = [
        ('0-1', '0-1 years'),
        ('1-2', '1-2 years'),
        ('2-3', '2-3 years')
    ]
    
    title = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    age_range = models.CharField(max_length=10, choices=AGE_RANGES)
    description = models.TextField()
    materials = models.TextField()
    safety_notes = models.TextField()
    benefits = models.TextField()
    modifications = models.TextField()
    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Physical Activities'

    def __str__(self):
        return f"{self.title} ({self.age_range})" 