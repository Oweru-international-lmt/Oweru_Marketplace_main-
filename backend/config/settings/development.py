import os
import ssl

from .base import *  # noqa: F403

DEBUG = env_bool("DEBUG", True)  # noqa: F405
ALLOWED_HOSTS = ALLOWED_HOSTS or ["localhost", "127.0.0.1", "testserver"]  # noqa: F405
SECURE_SSL_REDIRECT = False

if os.name == "nt":
    # Development only: Celery does not officially support Windows. The solo
    # pool keeps queued execution but has no prefork isolation or time limits.
    CELERY_WORKER_POOL = "solo"
    CELERY_WORKER_CONCURRENCY = 1

# Hosted development Redis must verify certificates, just as the production
# settings do. Local redis:// services do not need SSL options.
if CELERY_BROKER_URL.startswith("rediss://"):  # noqa: F405
    CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
if CELERY_RESULT_BACKEND.startswith("rediss://"):  # noqa: F405
    CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": ssl.CERT_REQUIRED}
