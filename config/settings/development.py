from .base import *  # noqa: F403

DEBUG = os.getenv("DEBUG", "true").lower() == "true"  # noqa: F405
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "testserver"]  # noqa: F405
SECURE_SSL_REDIRECT = False
