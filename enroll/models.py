from django.db import models
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings

# Create your models here.
class Student(models.Model):
    child_id = models.AutoField(primary_key=True)
    
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    child_name = models.CharField(max_length=100)
    date_of_birth = models.DateField() 
    child_address = models.CharField(max_length=100)
    child_gender = models.CharField(
        max_length=1, 
        choices=[('M', 'Male'), ('F', 'Female')],
        default='M'
    )
    
    parent_name = models.CharField(max_length=100)
    parent_address = models.CharField(max_length=100)
    parent_phone = models.CharField(max_length=128)
    parent_email = models.EmailField(max_length=100)
    ok_to_text = models.BooleanField(default=True)
    parent = models.BooleanField(default=True)
    caretaker = models.BooleanField(default=True)
    relative = models.BooleanField(default=True)
    guardian = models.BooleanField(default=True)
    other = models.BooleanField(default=True)
        
    parent_name_1 = models.CharField(max_length=100, null=True, blank=True)
    parent_phone_1 = models.CharField(max_length=128, null=True, blank=True)
    parent_email_1 = models.EmailField(max_length=100, null=True, blank=True)
    ok_to_text_1 = models.BooleanField(default=True, null=True, blank=True)
    authorized_pickup_1 = models.BooleanField(default=True, null=True, blank=True)

    parent_name_2 = models.CharField(max_length=100, null=True, blank=True)
    parent_phone_2 = models.CharField(max_length=128, null=True, blank=True)
    parent_email_2 = models.EmailField(max_length=100, null=True, blank=True)
    ok_to_text_2 = models.BooleanField(default=True, null=True, blank=True)
    authorized_pickup_2 = models.BooleanField(default=True, null=True, blank=True)

    parent_name_3 = models.CharField(max_length=100, null=True, blank=True)
    parent_phone_3 = models.CharField(max_length=128, null=True, blank=True)
    parent_email_3 = models.EmailField(max_length=100, null=True, blank=True)
    ok_to_text_3 = models.BooleanField(default=True, null=True, blank=True)
    authorized_pickup_3 = models.BooleanField(default=True, null=True, blank=True)
    
    date_of_enrollment = models.DateField(auto_now=False)
    date_of_withdrawal = models.DateField(auto_now=False)
                                          
    child_physician = models.CharField(max_length=100)
    child_physician_phone = models.CharField(max_length=128)
    preferred_hospital = models.CharField(max_length=100)
    hospital_phone = models.CharField(max_length=128)
    child_dentist = models.CharField(max_length=100)
    dentist_phone = models.CharField(max_length=128)
   
    child_allergies = models.CharField(max_length=100)
    speech_therapy = models.BooleanField(default=True)
    physical_therapy = models.BooleanField(default=True)
    early_intervention = models.BooleanField(default=True)
    other_therapy = models.BooleanField(default=True)
    none_therapy = models.BooleanField(default=True)
    
    info_to_share = models.TextField(max_length=100,null=True, blank=True)
   
    consent_to_treat = models.BooleanField(default=True)
    consent_to_transport = models.BooleanField(default=True)
    consent_to_trip = models.BooleanField(default=True)
    understand_permissions = models.BooleanField(default=True)   
    agree_to_update = models.BooleanField(default=True)
    agree_policies = models.BooleanField(default=True)
    photo_release = models.BooleanField(default=True)

    signature = models.CharField(max_length=100)
    date_signed = models.DateField(auto_now=False)

    enrolled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='enrolled_students'
    )
    enrollment_date = models.DateTimeField(auto_now_add=True)
    last_modified = models.DateTimeField(auto_now=True)
    last_modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='student_modifications'
    )

    def __str__(self):
        return self.child_name

    def save(self, *args, **kwargs):
        # Track who last modified the record
        if hasattr(self, '_current_user'):
            self.last_modified_by = self._current_user
        super().save(*args, **kwargs)

class Child(Student):
    """
    Child model that extends Student with additional attendance tracking fields.
    This uses multi-table inheritance.
    """
    is_checked_in = models.BooleanField(default=False)
    check_in_time = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        verbose_name = 'Child'
        verbose_name_plural = 'Children'

    def __str__(self):
        return self.child_name

class StudentRating(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    rating = models.IntegerField()

    def __str__(self):
        return f"{self.child} rated {self.rating}"

class ChildActivity(models.Model):
    """Scheduled activity for a child on a specific date, created from agent chat responses."""
    AGENT_CHOICES = [
        ('grace', 'Grace'),
        ('patience', 'Patience'),
        ('sage', 'Sage'),
    ]

    child = models.ForeignKey(Child, on_delete=models.CASCADE, related_name='scheduled_activities')
    title = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=50, blank=True, default='')
    agent = models.CharField(max_length=20, choices=AGENT_CHOICES)
    scheduled_date = models.DateField()
    description = models.TextField(blank=True, default='')
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    curriculum_entry = GenericForeignKey('content_type', 'object_id')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['scheduled_date', 'title']

    def __str__(self):
        return f"{self.child.child_name} - {self.title} ({self.scheduled_date})"


class AttendanceLog(models.Model):
    child = models.ForeignKey(
        Child, 
        on_delete=models.CASCADE,
        related_name='attendance_logs'
    )
    check_in = models.DateTimeField()
    check_out = models.DateTimeField(null=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-check_in']
    
    def __str__(self):
        return f"{self.child.child_name} - {self.check_in.date()}"
    

