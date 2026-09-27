from django.contrib.admin.apps import AdminConfig


class MateralleAdminConfig(AdminConfig):
    """Use our custom AdminSite that restricts access to ADMINISTRATOR role."""
    default_site = 'website.admin_site.MateralleAdminSite'
