from django.contrib import admin
from .models import Student, ChildActivity
# Register your models here.
admin.site.register (Student)

@admin.register(ChildActivity)
class ChildActivityAdmin(admin.ModelAdmin):
    list_display = ['child', 'title', 'agent', 'scheduled_date', 'activity_type']
    list_filter = ['agent', 'scheduled_date', 'activity_type']
    search_fields = ['title', 'child__child_name']