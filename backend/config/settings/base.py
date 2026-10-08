import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    return int(os.getenv(name, str(default)))


def env_list(name, default=None):
    value = os.getenv(name)
    if value is None:
        return list(default or [])
    return [item.strip() for item in value.split(",") if item.strip()]


SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in the environment.")

DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.gis",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "apps.accounts.apps.AccountsConfig",
    "apps.audit.apps.AuditConfig",
    "apps.common.apps.CommonConfig",
    "apps.localities.apps.LocalitiesConfig",
    "apps.lister_identity.apps.ListerIdentityConfig",
    "apps.local_officials.apps.LocalOfficialsConfig",
    "apps.listings.apps.ListingsConfig",
    "apps.media.apps.MediaConfig",
    "apps.leads.apps.LeadsConfig",
    "apps.deals.apps.DealsConfig",
    "apps.commissions.apps.CommissionsConfig",
    "apps.payments.apps.PaymentsConfig",
    "apps.properties.apps.PropertiesConfig",
    "apps.site_capture.apps.SiteCaptureConfig",
    "apps.professionals.apps.ProfessionalsConfig",
    "apps.verification.apps.VerificationConfig",
    "apps.roles.apps.RolesConfig",
    "apps.roles.legacy_authorization.apps.AuthorizationConfig",
    "apps.audit.legacy_event_stream.apps.AuditConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.auth.context_processors.auth",
        "django.contrib.messages.context_processors.messages",
    ]},
}]

DATABASES = {"default": {
    "ENGINE": os.getenv("POSTGRES_ENGINE", "django.contrib.gis.db.backends.postgis"),
    "NAME": os.getenv("POSTGRES_DB", ""),
    "USER": os.getenv("POSTGRES_USER", ""),
    "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
    "HOST": os.getenv("POSTGRES_HOST", ""),
    "PORT": os.getenv("POSTGRES_PORT", "5432"),
    "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
}}
if os.getenv("DATABASE_URL"):
    from urllib.parse import urlparse

    database_url = urlparse(os.environ["DATABASE_URL"])
    if database_url.scheme not in {"postgres", "postgresql", "postgis"}:
        raise RuntimeError("DATABASE_URL must use PostgreSQL/PostGIS.")
    DATABASES["default"].update({
        "ENGINE": "django.contrib.gis.db.backends.postgis",
        "NAME": database_url.path.lstrip("/"),
        "USER": database_url.username or "",
        "PASSWORD": database_url.password or "",
        "HOST": database_url.hostname or "localhost",
        "PORT": str(database_url.port or 5432),
    })

AUTH_USER_MODEL = "accounts.User"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]
ACCOUNT_LOGIN_MAX_ATTEMPTS = env_int("ACCOUNT_LOGIN_MAX_ATTEMPTS", 5)
ACCOUNT_LOGIN_LOCKOUT_MINUTES = env_int("ACCOUNT_LOGIN_LOCKOUT_MINUTES", 15)
ACCOUNT_EMAIL_VERIFICATION_MINUTES = env_int("ACCOUNT_EMAIL_VERIFICATION_MINUTES", 60)
LISTER_IDENTITY_VALIDITY_MONTHS = env_int("LISTER_IDENTITY_VALIDITY_MONTHS", 12)
LISTER_IDENTITY_EXPIRY_REMINDER_DAYS = env_int("LISTER_IDENTITY_EXPIRY_REMINDER_DAYS", 30)
PROPERTY_DOCUMENT_VERIFICATION_VALIDITY_MONTHS = env_int("PROPERTY_DOCUMENT_VERIFICATION_VALIDITY_MONTHS", 12)
PROPERTY_FIELD_VERIFICATION_VALIDITY_MONTHS = env_int("PROPERTY_FIELD_VERIFICATION_VALIDITY_MONTHS", 12)

from celery.schedules import crontab
CELERY_BEAT_SCHEDULE = {
    "verification-level-recalculation": {"task": "apps.verification.tasks.recalculate_verification_levels", "schedule": crontab(hour=0, minute=30)},
    "verification-nightly-expiry": {"task": "apps.verification.tasks.process_document_verification_expiry", "schedule": crontab(hour=0, minute=15)},
    "full-check-deadlines": {"task": "apps.verification.tasks.process_full_check_deadlines", "schedule": crontab(minute="*/15")},
}
LEAD_LOST_REVIEW_MONTHS = env_int("LEAD_LOST_REVIEW_MONTHS", 6)
PAYOUT_WORKING_DAYS = env_int("PAYOUT_WORKING_DAYS", 3)
PAYOUT_HOLIDAYS = env_list("PAYOUT_HOLIDAYS")
OWNER_CONFIRMATION_DAYS = env_int("OWNER_CONFIRMATION_DAYS", 7)
OWNER_CONFIRMATION_URL = os.getenv("OWNER_CONFIRMATION_URL", "")

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_VERSIONING_CLASS": "rest_framework.versioning.URLPathVersioning",
    "DEFAULT_VERSION": "v1",
    "ALLOWED_VERSIONS": ["v1"],
    "VERSION_PARAM": "version",
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"anon": "120/hour", "user": "1200/hour", "auth_login": "10/minute", "auth_register": "5/hour", "confirmation": "20/hour"},
}
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Oweru Marketplace API",
    "DESCRIPTION": "Versioned API foundation for the Oweru Marketplace.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "COMPONENT_SPLIT_REQUEST": True,
}

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300

CORS_ALLOW_ALL_ORIGINS = False
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = env_bool("CORS_ALLOW_CREDENTIALS", False)
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("sw", "Kiswahili")]
TIME_ZONE = "Africa/Dar_es_Salaam"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "private_media"
MEDIA_URL = "/media/"
MEDIA_STORAGE_BACKEND = os.getenv("MEDIA_STORAGE_BACKEND", "unconfigured")
MEDIA_STORAGE_BUCKET = os.getenv("MEDIA_STORAGE_BUCKET", "")
MEDIA_STORAGE_ENDPOINT = os.getenv("MEDIA_STORAGE_ENDPOINT", "")
MEDIA_SIGNED_URL_TTL_SECONDS = env_int("MEDIA_SIGNED_URL_TTL_SECONDS", 300)
MEDIA_MAX_UPLOAD_BYTES = env_int("MEDIA_MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
MEDIA_ALLOWED_IMAGE_MIME_TYPES = env_list(
    "MEDIA_ALLOWED_IMAGE_MIME_TYPES",
    ["image/jpeg", "image/png", "image/webp"],
)
MEDIA_MAX_IMAGE_WIDTH = env_int("MEDIA_MAX_IMAGE_WIDTH", 2048)
MEDIA_MAX_IMAGE_HEIGHT = env_int("MEDIA_MAX_IMAGE_HEIGHT", 2048)
PROPERTY_DUPLICATE_DISTANCE_METERS = env_int("PROPERTY_DUPLICATE_DISTANCE_METERS", 50)
PROPERTY_DUPLICATE_SIZE_DIFFERENCE_PERCENT = env_int("PROPERTY_DUPLICATE_SIZE_DIFFERENCE_PERCENT", 10)
PUBLIC_LISTING_PAGE_SIZE = env_int("PUBLIC_LISTING_PAGE_SIZE", 20)
PUBLIC_LISTING_MAX_PAGE_SIZE = env_int("PUBLIC_LISTING_MAX_PAGE_SIZE", 100)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = env_int("EMAIL_PORT", 25)
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "false").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@oweru.example")
PASSWORD_RESET_URL = os.getenv("PASSWORD_RESET_URL", "")
EMAIL_VERIFICATION_URL = os.getenv("EMAIL_VERIFICATION_URL", "")
PASSWORD_RESET_TIMEOUT = 60 * 60

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"json": {"()": "apps.common.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
