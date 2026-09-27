from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Student, Child


@receiver(post_save, sender=Student)
def create_child_for_student(sender, instance, created, **kwargs):
    """Auto-create a Child record when a Student is enrolled."""
    if created:
        # Only create if a Child doesn't already exist for this Student
        if not Child.objects.filter(student_ptr=instance).exists():
            Child(student_ptr=instance, is_checked_in=False, check_in_time=None).save_base(raw=True)
