import os

os.environ.setdefault("SECRET_KEY", "test-only-not-for-deployment")

from .base import *  # noqa: F403

SECRET_KEY = "test-only-not-for-deployment-with-at-least-32-bytes"
DEBUG = env_bool("DEBUG", False)  # noqa: F405
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", ["testserver", "localhost"])  # noqa: F405
DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": ":memory:"}}
CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}}
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
PASSWORD_RESET_URL = "https://example.test/reset-password"
EMAIL_VERIFICATION_URL = "https://example.test/verify-email"
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
