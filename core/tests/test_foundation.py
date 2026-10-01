import json
import logging

import pytest
from django.conf import settings
from config.settings import base as base_settings
from core.logging import JsonFormatter
from rest_framework.test import APIClient


pytestmark = pytest.mark.django_db


def test_api_is_versioned_and_root_is_public():
    response = APIClient().get("/api/v1/")
    assert response.status_code == 200
    assert response.data["version"] == "v1"
    assert APIClient().get("/api/v2/").status_code == 404


def test_live_health_check_does_not_require_services():
    response = APIClient().get("/api/v1/health/live/")
    assert response.status_code == 200
    assert response.data == {"status": "ok"}


def test_openapi_and_swagger_endpoints_are_available():
    assert APIClient().get("/api/schema/").status_code == 200
    assert APIClient().get("/api/docs/").status_code == 200


def test_settings_include_security_cors_postgis_and_celery_foundation():
    assert base_settings.DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
    assert settings.DATABASES["default"]["ENGINE"] == "django.db.backends.sqlite3"
    assert "corsheaders" in settings.INSTALLED_APPS
    assert settings.SECURE_CONTENT_TYPE_NOSNIFF
    assert settings.X_FRAME_OPTIONS == "DENY"
    assert settings.CELERY_BROKER_URL.startswith("redis://")
    assert settings.REDIS_URL.startswith("redis://")
    from config.celery import app

    assert app.main == "oweru_marketplace"


def test_structured_logging_emits_json():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "service ready", (), None)
    payload = json.loads(JsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert payload["message"] == "service ready"
    assert payload["logger"] == "test"
