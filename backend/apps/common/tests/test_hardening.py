import json
import logging
from unittest.mock import patch
import pytest
from django.core.cache import cache
from django.test import override_settings
from rest_framework.test import APIClient
from apps.common.logging import JsonFormatter
from config.production_validation import validate

pytestmark = pytest.mark.django_db


def valid_config():
    return {"SECRET_KEY": "production-validation-fixture-with-50-distinct-safe-characters-0123456789", "MARKETPLACE_PUBLIC_URL": "https://market.example.test", "PASSWORD_RESET_URL": "https://market.example.test/reset-password", "EMAIL_VERIFICATION_URL": "https://market.example.test/verify-email", "OWNER_CONFIRMATION_URL": "https://market.example.test/confirm", "CORS_ALLOWED_ORIGINS": ["https://market.example.test"], "CSRF_TRUSTED_ORIGINS": ["https://market.example.test"], "DATABASES": {"default": {"ENGINE": "django.contrib.gis.db.backends.postgis", "NAME": "fixture", "USER": "fixture", "PASSWORD": "fixture", "HOST": "db.example.test", "OPTIONS": {"sslmode": "verify-full"}}}, "REDIS_URL": "rediss://:fixture@redis.example.test/0", "CELERY_BROKER_URL": "rediss://:fixture@redis.example.test/1", "CELERY_RESULT_BACKEND": "rediss://:fixture@redis.example.test/2", "MEDIA_STORAGE_BACKEND": "s3", "MEDIA_STORAGE_BUCKET": "fixture", "MEDIA_SIGNED_URL_TTL_SECONDS": 300, "EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend", "EMAIL_HOST": "smtp.example.test", "EMAIL_USE_TLS": True, "EMAIL_USE_SSL": False, "DEFAULT_FROM_EMAIL": "no-reply@example.test"}


def test_valid_configuration_and_no_secret_values_in_rejection():
    validate(valid_config())
    bad = valid_config()
    bad["SECRET_KEY"] = "secret-do-not-print"
    with pytest.raises(RuntimeError) as exc:
        validate(bad)
    assert "secret-do-not-print" not in str(exc.value)


@pytest.mark.parametrize("key,value", [("MARKETPLACE_PUBLIC_URL", "http://example.test"), ("MEDIA_STORAGE_BACKEND", "memory"), ("MEDIA_SIGNED_URL_TTL_SECONDS", 301), ("CORS_ALLOWED_ORIGINS", ["https://*.example.test"]), ("CSRF_TRUSTED_ORIGINS", []), ("REDIS_URL", "redis://:fixture@host/0"), ("EMAIL_USE_SSL", True)])
def test_unsafe_production_configuration_rejected(key, value):
    values = valid_config()
    values[key] = value
    with pytest.raises(RuntimeError):
        validate(values)


def test_empty_smtp_sender_is_rejected():
    values = valid_config()
    values["DEFAULT_FROM_EMAIL"] = ""
    with pytest.raises(RuntimeError):
        validate(values)


def test_request_observability_omits_tokens_body_and_user_identifiers(caplog):
    with caplog.at_level(logging.INFO, logger="apps.common.requests"):
        result = APIClient().get("/api/v1/health/live/?token=private-capability", HTTP_AUTHORIZATION="Bearer private-secret", HTTP_X_REQUEST_ID="attacker-controlled")
    assert len(result["X-Request-ID"]) == 32 and result["X-Request-ID"] != "attacker-controlled"
    record = next(row for row in caplog.records if row.name == "apps.common.requests")
    payload = JsonFormatter().format(record)
    assert "private-capability" not in payload and "private-secret" not in payload
    assert '"duration_ms"' in payload and '"route"' in payload


def test_json_logging_redacts_common_secrets_and_exception_messages():
    record = logging.LogRecord("test", logging.ERROR, __file__, 1, "Bearer secret-token token?token=secret-query user@example.test", (), (RuntimeError, RuntimeError("password=secret-value"), None))
    payload = JsonFormatter().format(record)
    assert "secret-token" not in payload and "secret-query" not in payload and "user@example.test" not in payload and "secret-value" not in payload
    assert json.loads(payload)["exception_type"] == "RuntimeError"


def test_refresh_has_scoped_limit_and_public_browsing_keeps_recent_behavior():
    from apps.accounts.token_views import LimitedTokenRefreshView
    cache.clear()
    client = APIClient()
    for _ in range(31):
        response = client.post("/api/v1/auth/token/refresh/", {"refresh": "invalid"}, format="json")
    assert response.status_code == 429 and LimitedTokenRefreshView.throttle_scope == "auth_refresh"
    assert client.get("/api/v1/public/listings/").status_code == 200
    cache.clear()


def test_sensitive_responses_no_store():
    assert APIClient().post("/api/v1/auth/login/", {}, format="json")["Cache-Control"] == "no-store"
