from django.contrib import admin
from .models import Dish, WeeklyPlanEntry
# Register your models here.
admin.site.register (Dish)

@admin.register(WeeklyPlanEntry)
class WeeklyPlanEntryAdmin(admin.ModelAdmin):
    list_display = ['scheduled_date', 'start_time', 'agent', 'title', 'is_static']
    list_filter = ['agent', 'is_static', 'week_start_date']
    search_fields = ['title']