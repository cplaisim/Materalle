from django.apps import AppConfig


class EnrollConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "enroll"

    def ready(self):
        import enroll.signals  # noqa: F401
