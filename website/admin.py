from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth.models import User
from .models import UserProfile, Document, LearningSession, Interaction

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Profile'

class CustomUserAdmin(UserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'get_role')
    list_filter = ('userprofile__role', 'is_staff', 'is_superuser', 'is_active', 'groups')

    def get_role(self, obj):
        try:
            if hasattr(obj, 'userprofile') and obj.userprofile:
                return obj.userprofile.role
        except UserProfile.DoesNotExist:
            pass
        except AttributeError:
            pass
        return None
    get_role.short_description = 'Role'
    get_role.admin_order_field = 'userprofile__role'

class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'uploaded_at')
    list_filter = ('uploaded_at',)
    search_fields = ('title',)
    readonly_fields = ('uploaded_at',)
    date_hierarchy = 'uploaded_at'

class LearningSessionAdmin(admin.ModelAdmin):
    list_display = ('user', 'start_time', 'end_time')
    list_filter = ('user', 'start_time')
    search_fields = ('user__username',)
    readonly_fields = ('start_time',)

class InteractionAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'timestamp')
    list_filter = ('user', 'action', 'timestamp')
    search_fields = ('user__username', 'action', 'details')
    readonly_fields = ('timestamp',)

# Unregister default User admin, re-register with custom
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)

# Register other models
admin.site.register(Document, DocumentAdmin)
admin.site.register(LearningSession, LearningSessionAdmin)
admin.site.register(Interaction, InteractionAdmin)
