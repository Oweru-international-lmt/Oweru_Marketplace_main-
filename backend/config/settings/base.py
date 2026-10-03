import os
from datetime import timedelta
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY must be set in the environment.")

DEBUG = False
ALLOWED_HOSTS = [host.strip() for host in os.getenv("ALLOWED_HOSTS", "").split(",") if host.strip()]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",
    "django_filters",
    "drf_spectacular",
    "accounts.apps.AccountsConfig",
    "authorization.apps.AuthorizationConfig",
    "audit.apps.AuditConfig",
    "core.apps.CoreConfig",
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
    # PostGIS is installed as a PostgreSQL extension. GeoDjango's optional
    # engine requires native GDAL/GEOS libraries, which are deployment-image
    # concerns and are not needed by the M01–M03 schemas.
    "ENGINE": os.getenv("POSTGRES_ENGINE", "django.db.backends.postgresql"),
    "NAME": os.getenv("POSTGRES_DB", "oweru_marketplace"),
    "USER": os.getenv("POSTGRES_USER", "oweru"),
    "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
    "HOST": os.getenv("POSTGRES_HOST", "localhost"),
    "PORT": os.getenv("POSTGRES_PORT", "5432"),
    "CONN_MAX_AGE": int(os.getenv("DB_CONN_MAX_AGE", "60")),
}}
if os.getenv("DATABASE_URL"):
    from urllib.parse import urlparse

    database_url = urlparse(os.environ["DATABASE_URL"])
    if database_url.scheme not in {"postgres", "postgresql", "postgis"}:
        raise RuntimeError("DATABASE_URL must use PostgreSQL/PostGIS.")
    DATABASES["default"].update({
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

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": ["accounts.authentication.MarketplaceJWTAuthentication"],
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
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/hour",
        "user": "1200/hour",
        "auth_login": "10/minute",
        "auth_register": "5/hour",
        "confirmation": "20/hour",
        "email_resend": "5/hour",
    },
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
}

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
CACHES = {"default": {"BACKEND": "django.core.cache.backends.redis.RedisCache", "LOCATION": REDIS_URL}}
CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300

CORS_ALLOWED_ORIGINS = [origin.strip() for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",") if origin.strip()]
CORS_ALLOW_CREDENTIALS = False
CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in os.getenv("CSRF_TRUSTED_ORIGINS", "").split(",") if origin.strip()]

LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("sw", "Kiswahili")]
TIME_ZONE = "Africa/Dar_es_Salaam"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_ROOT = BASE_DIR / "private_media"
MEDIA_URL = "/media/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "25"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "false").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", "no-reply@oweru.example")
PASSWORD_RESET_URL = os.getenv("PASSWORD_RESET_URL", "")
# ACC-03: email reset links expire after 30 minutes.
PASSWORD_RESET_TIMEOUT = 30 * 60
# ACC-05 email confirmation link (frontend page that posts id and token back).
EMAIL_CONFIRMATION_URL = os.getenv("EMAIL_CONFIRMATION_URL", "")
EMAIL_CONFIRMATION_LIFETIME = timedelta(hours=int(os.getenv("EMAIL_CONFIRMATION_LIFETIME_HOURS", "72")))
# SRD 20.3 WhatsApp confirmation page link; links expire after 7 days by default.
CONFIRMATION_URL = os.getenv("CONFIRMATION_URL", "")
PHONE_CONFIRMATION_LIFETIME = timedelta(days=int(os.getenv("PHONE_CONFIRMATION_LIFETIME_DAYS", "7")))

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
    "formatters": {"json": {"()": "core.logging.JsonFormatter"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "json"}},
    "root": {"handlers": ["console"], "level": os.getenv("LOG_LEVEL", "INFO")},
}
