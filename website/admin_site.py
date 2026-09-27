from django.contrib.admin import AdminSite

from materalleapp.user_utils import is_admin


class MateralleAdminSite(AdminSite):
    """Only allow users with the ADMINISTRATOR role to access /admin/."""

    def has_permission(self, request):
        if not super().has_permission(request):
            return False
        # Prefer role-based check; fall back to superuser flag for bootstrap.
        if is_admin(request.user):
            return True
        return getattr(request.user, "is_superuser", False)
