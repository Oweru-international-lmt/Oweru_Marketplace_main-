from .base import *  # noqa: F403

DEBUG = False
if not ALLOWED_HOSTS:  # noqa: F405
    raise RuntimeError("ALLOWED_HOSTS must be configured in production.")
if "*" in ALLOWED_HOSTS:  # noqa: F405
    raise RuntimeError("Wildcard ALLOWED_HOSTS is not allowed in production.")
if not CORS_ALLOWED_ORIGINS:  # noqa: F405
    raise RuntimeError("CORS_ALLOWED_ORIGINS must be configured in production.")
if CORS_ALLOW_ALL_ORIGINS:  # noqa: F405
    raise RuntimeError("CORS_ALLOW_ALL_ORIGINS is not allowed in production.")
if not PASSWORD_RESET_URL:  # noqa: F405
    raise RuntimeError("PASSWORD_RESET_URL must be configured in production.")
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https") if env_bool("TRUST_PROXY_SSL_HEADER", False) else None
DATABASES["default"].setdefault("OPTIONS", {}).update({"sslmode": os.getenv("POSTGRES_SSLMODE", "verify-full"), "connect_timeout": 5})
if os.getenv("POSTGRES_SSLROOTCERT"):
    DATABASES["default"]["OPTIONS"]["sslrootcert"] = os.environ["POSTGRES_SSLROOTCERT"]
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True
CACHES["default"]["OPTIONS"] = {"socket_connect_timeout": 3, "socket_timeout": 3}
from config.production_validation import validate
validate(globals())
import ssl
CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
