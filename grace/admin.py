from django.contrib import admin
from .models import SocialCurriculum


@admin.register(SocialCurriculum)
class SocialCurriculumAdmin(admin.ModelAdmin):
    list_display = ('title', 'activity_type', 'age_range', 'duration_minutes', 'created_by', 'created_at')
    list_filter = ('activity_type', 'age_range')
    search_fields = ('title', 'description', 'developmental_goal')
