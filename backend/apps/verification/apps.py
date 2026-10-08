from django.apps import AppConfig


class VerificationConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.verification"
    label = "verification"

    def ready(self):
        from . import signals  # noqa: F401
        from django.db.models.signals import post_migrate
        from .levels import initialize_levels
        post_migrate.connect(initialize_levels, sender=self, dispatch_uid="verification.initial_level_snapshots")
