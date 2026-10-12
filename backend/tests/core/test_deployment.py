import os
from pathlib import Path
import subprocess
import json
import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from io import StringIO
from apps.professionals.tests.test_professionals import account
from apps.marketing.models import CampaignDelivery
from apps.common.management.commands.operational_status import status

pytestmark = pytest.mark.django_db


def test_production_preflight_rejects_nonproduction_settings():
    with pytest.raises(CommandError):
        call_command("production_preflight", offline=True)


def test_operator_counters_empty_and_non_personal():
    user = account("buyer")
    payload = status()
    assert payload["analytics_stale"] and payload["outbox_waiting"] == 0
    assert user.email not in str(payload) and user.phone not in str(payload)
    output = StringIO()
    call_command("operational_status", stdout=output)
    assert json.loads(output.getvalue())["failed_campaign_emails"] == 0


def test_required_periodic_tasks_are_registered_and_scheduled_once():
    from django.conf import settings
    from config.celery import app
    app.loader.import_default_modules()
    tasks = [entry["task"] for entry in settings.CELERY_BEAT_SCHEDULE.values()]
    for task in ["apps.lister_identity.tasks.process_lister_identity_expiry", "apps.payments.tasks.payout_due_check", "apps.payments.tasks.lost_sold_review", "apps.analytics.tasks.refresh_market_aggregates", "apps.marketing.tasks.deliver_campaigns"]:
        assert tasks.count(task) == 1
        assert task in app.tasks


def test_production_configuration_offline_boot_and_deploy_checks():
    environment = {**os.environ, "DJANGO_SETTINGS_MODULE": "config.settings.production", "SECRET_KEY": "isolated-production-config-fixture-not-live-01234567890123456789", "ALLOWED_HOSTS": "api.example.test", "MARKETPLACE_PUBLIC_URL": "https://market.example.test", "PASSWORD_RESET_URL": "https://market.example.test/reset-password", "EMAIL_VERIFICATION_URL": "https://market.example.test/verify-email", "OWNER_CONFIRMATION_URL": "https://market.example.test/confirm", "CORS_ALLOWED_ORIGINS": "https://market.example.test", "CSRF_TRUSTED_ORIGINS": "https://market.example.test", "POSTGRES_DB": "offline", "POSTGRES_USER": "offline", "POSTGRES_PASSWORD": "offline-fixture", "POSTGRES_HOST": "db.example.test", "POSTGRES_SSLMODE": "verify-full", "REDIS_URL": "rediss://:fixture@redis.example.test/0", "CELERY_BROKER_URL": "rediss://:fixture@redis.example.test/1", "CELERY_RESULT_BACKEND": "rediss://:fixture@redis.example.test/2", "MEDIA_STORAGE_BACKEND": "s3", "MEDIA_STORAGE_BUCKET": "offline-fixture", "MEDIA_STORAGE_ENDPOINT": "", "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend", "EMAIL_HOST": "smtp.example.test", "EMAIL_USE_TLS": "true", "EMAIL_USE_SSL": "false", "DEFAULT_FROM_EMAIL": "no-reply@example.test"}
    environment.pop("DATABASE_URL", None)
    result = subprocess.run([os.sys.executable, "-B", "manage.py", "production_preflight", "--offline"], cwd=Path(__file__).resolve().parents[2], env=environment, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "external services and launch acceptance are unverified" in result.stdout
