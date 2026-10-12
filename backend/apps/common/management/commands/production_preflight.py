from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.core.cache import cache
from django.db import connection
import re


class Command(BaseCommand):
    help = "Read-only production configuration/service checks; never applies migrations or sends messages."

    def add_arguments(self, parser):
        parser.add_argument("--offline", action="store_true", help="Check configuration only; no service readiness claim.")

    def handle(self, **options):
        if settings.SETTINGS_MODULE != "config.settings.production":
            raise CommandError("Select config.settings.production for this preflight.")
        from config.production_validation import validate
        try:
            validate({name: getattr(settings, name) for name in ["SECRET_KEY", "MARKETPLACE_PUBLIC_URL", "PASSWORD_RESET_URL", "EMAIL_VERIFICATION_URL", "OWNER_CONFIRMATION_URL", "CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS", "DATABASES", "REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND", "MEDIA_STORAGE_BACKEND", "MEDIA_STORAGE_BUCKET", "MEDIA_STORAGE_ENDPOINT", "MEDIA_SIGNED_URL_TTL_SECONDS", "EMAIL_BACKEND", "EMAIL_HOST", "EMAIL_USE_TLS", "EMAIL_USE_SSL", "DEFAULT_FROM_EMAIL"]})
            call_command("check", fail_level="ERROR", stdout=self.stdout)
            call_command("check", deploy=True, tags=["security"], fail_level="WARNING", stdout=self.stdout)
            if options["offline"]:
                self.stdout.write("Configuration passed; external services and launch acceptance are unverified.")
                return
            call_command("migrate", check=True, stdout=self.stdout)
            with connection.cursor() as cursor:
                cursor.execute("SELECT PostGIS_Version()")
                cursor.fetchone()
            # Cache write is transient, contains no data and does not alter domain records.
            cache.set("health:preflight", "ready", timeout=5)
            if cache.get("health:preflight") != "ready":
                raise RuntimeError("Cache readiness failed")
        except Exception as exc:
            check_ids = sorted(set(re.findall(r"\b[a-z_]+\.[WE]\d{3}\b", str(exc))))
            raise CommandError(f"Preflight failed ({type(exc).__name__}); checks: {', '.join(check_ids) or 'service/configuration'}. No secret values are reported.") from None
        self.stdout.write("Configuration, migration state, PostGIS and Redis passed. SMTP/storage/backup/restore evidence remains required.")
