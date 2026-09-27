from django.db import models
from enroll.models import Child
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
import json

# Create your models here.
class GroceryItem(models.Model):
    CATEGORIES = [
        ('VEGETABLE', 'Vegetable'),
        ('FRUIT', 'Fruit'),
        ('GRAIN', 'Grain'),
        ('PROTEIN', 'Protein'),
        ('DRINK', 'Drink'),
        ('OTHER', 'Other')
    ]
    name = models.CharField(max_length=100)
    category = models.CharField(max_length=20, choices=CATEGORIES)
    added_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    added_at = models.DateTimeField(auto_now_add=True)
    is_default = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} ({self.category})"

class Dish(models.Model):
    MEAL_TYPE_CHOICES = [
        ('BREAKFAST', 'Breakfast'),
        ('AM_SNACK', 'AM Snack'),
        ('LUNCH', 'Lunch'),
        ('PM_SNACK', 'PM Snack'),
        ('SUPPER', 'Supper'),
    ]
    title = models.CharField(max_length=200, blank=True, null=True)
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES, blank=True, default='')
    vegetable = models.CharField(max_length=100, blank=True, null=True)
    fruit = models.CharField(max_length=100, blank=True, null=True)
    grain = models.CharField(max_length=100, blank=True, null=True)
    protein = models.CharField(max_length=100, blank=True, null=True)
    drink = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    def save(self, *args, **kwargs):
        if not self.title:
            parts = [p for p in [self.protein, self.grain] if p]
            self.title = ' & '.join(parts) if parts else 'Untitled Dish'
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title or f"Dish with {self.vegetable}, {self.fruit}, {self.grain}, {self.protein}, {self.drink}"

class Menu(models.Model):
    """
    Model to store generated menus
    """
    # Basic information
    title = models.CharField(max_length=200)
    provider_name = models.CharField(max_length=200)
    provider_address = models.CharField(max_length=200)
    month_year = models.CharField(max_length=10)  # Format: "Feb-25"
    
    # Menu data stored as JSON
    menu_data_json = models.TextField()
    
    # Metadata
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    is_current = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    @property
    def menu_data(self):
        """
        Return the menu data as a Python dictionary
        """
        return json.loads(self.menu_data_json)
    
    @menu_data.setter
    def menu_data(self, value):
        """
        Set the menu data from a Python dictionary
        """
        self.menu_data_json = json.dumps(value)
    
    def __str__(self):
        return f"{self.provider_name} - {self.month_year}"
    
    class Meta:
        ordering = ['-created_at']

class Meal(models.Model):
    MEAL_TYPES = [
        ('BREAKFAST', 'Breakfast'),
        ('AM_SNACK', 'AM Snack'),
        ('LUNCH', 'Lunch'),
        ('PM_SNACK', 'PM Snack'),
        ('SUPPER', 'Supper')
    ]
    name = models.CharField(max_length=200)
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPES)
    date = models.DateField()
    children = models.ManyToManyField('enroll.Child', through='MealAttendance')
    created_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)

class MealAttendance(models.Model):
    child = models.ForeignKey(Child, on_delete=models.CASCADE)
    meal = models.ForeignKey(Meal, on_delete=models.CASCADE)
    attended = models.BooleanField(default=False)
    recorded_by = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    recorded_at = models.DateTimeField(auto_now_add=True)

class Schedule(models.Model):
    AGENT_CHOICES = [
        ('grace', 'Grace'),
        ('patience', 'Patience'),
        ('sage', 'Sage'),
        ('', 'None'),
    ]

    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'),
    ]

    start_time = models.TimeField()
    end_time = models.TimeField()
    activity = models.CharField(max_length=200, blank=True, default='')
    agent = models.CharField(max_length=20, choices=AGENT_CHOICES, blank=True, default='')
    day_of_week = models.IntegerField(choices=DAY_CHOICES)  # 0 = Monday, 4 = Friday
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ['day_of_week', 'start_time']
        unique_together = ['start_time', 'day_of_week', 'is_default']

    def __str__(self):
        days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        day = days[self.day_of_week] if self.day_of_week < len(days) else '?'
        return f"{day} {self.start_time.strftime('%I:%M %p')}: {self.activity}"

class Document(models.Model):
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='uploads/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    file_type = models.CharField(max_length=50, blank=True)
    file_size = models.IntegerField(default=0)
    uploaded_by = models.ForeignKey(
        'auth.User',
        on_delete=models.CASCADE,
        related_name='sage_documents',
        null=True,  # Allow null for existing records
    )
    analysis = models.TextField(blank=True, null=True)  # Add field to store analysis results

    def save(self, *args, **kwargs):
        if self.file:
            self.file_type = self.file.name.split('.')[-1].lower()
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

class WeeklyPlanEntry(models.Model):
    """A single activity cell in a generated weekly schedule."""
    AGENT_CHOICES = [
        ('grace', 'Grace'),
        ('patience', 'Patience'),
        ('sage', 'Sage'),
    ]

    week_start_date = models.DateField()  # Monday of the week
    scheduled_date = models.DateField()   # Specific day
    start_time = models.TimeField()
    agent = models.CharField(max_length=20, choices=AGENT_CHOICES)
    title = models.CharField(max_length=200)
    activity_type = models.CharField(max_length=50, blank=True, default='')
    description = models.TextField(blank=True, default='')
    is_static = models.BooleanField(default=False)  # True for Sage admin tasks
    guideline_activity = models.CharField(max_length=200, blank=True, default='')  # Original guideline slot name
    children = models.ManyToManyField('enroll.Child', blank=True, related_name='weekly_activities')
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True)
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        ordering = ['scheduled_date', 'start_time']

    def __str__(self):
        return f"{self.scheduled_date} {self.start_time.strftime('%I:%M %p')} - {self.title} ({self.agent})"


class Attendance(models.Model):
    student = models.ForeignKey(Child, on_delete=models.CASCADE)
    date = models.DateField()
    check_in = models.DateTimeField(null=True, blank=True)
    check_out = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['date']
