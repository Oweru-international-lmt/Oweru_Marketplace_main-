from urllib.parse import urlsplit
from django.core.validators import validate_email
from django.core.exceptions import ValidationError


def validate(values):
    """Fail before starting a production process; never include secret values."""
    errors = []
    secret = values.get("SECRET_KEY", "")
    if len(secret) < 50 or len(set(secret)) < 5 or secret.startswith("django-insecure-") or "test-only" in secret:
        errors.append("SECRET_KEY must be a strong production secret")
    for name in ["MARKETPLACE_PUBLIC_URL", "PASSWORD_RESET_URL", "EMAIL_VERIFICATION_URL", "OWNER_CONFIRMATION_URL"]:
        url = urlsplit(values.get(name, ""))
        if url.scheme != "https" or not url.hostname or url.username or url.password or url.query or url.fragment:
            errors.append(name + " must be an absolute HTTPS URL without credentials/query/fragment")
    for name in ["CORS_ALLOWED_ORIGINS", "CSRF_TRUSTED_ORIGINS"]:
        origins = values.get(name, [])
        if not origins:
            errors.append(name + " is required")
        for value in origins:
            url = urlsplit(value)
            if url.scheme != "https" or not url.hostname or "*" in value or url.username or url.password or url.path or url.query or url.fragment:
                errors.append(name + " requires explicit HTTPS origins")
                break
    db = values.get("DATABASES", {}).get("default", {})
    if db.get("ENGINE") != "django.contrib.gis.db.backends.postgis" or not all(db.get(name) for name in ["NAME", "USER", "PASSWORD", "HOST"]):
        errors.append("Configure a PostgreSQL/PostGIS database and authenticated connection")
    if db.get("OPTIONS", {}).get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        errors.append("PostgreSQL transport encryption is required")
    for name in ["REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"]:
        url = urlsplit(values.get(name, ""))
        if url.scheme != "rediss" or not url.hostname or not url.password:
            errors.append(name + " requires authenticated Redis over TLS")
    if values.get("MEDIA_STORAGE_BACKEND") != "s3" or not values.get("MEDIA_STORAGE_BUCKET"):
        errors.append("Configure private S3-compatible media storage")
    endpoint = values.get("MEDIA_STORAGE_ENDPOINT", "")
    if endpoint and urlsplit(endpoint).scheme != "https":
        errors.append("MEDIA_STORAGE_ENDPOINT must use HTTPS")
    if not 1 <= values.get("MEDIA_SIGNED_URL_TTL_SECONDS", 0) <= 300:
        errors.append("Private media signed URLs must expire within 300 seconds")
    if values.get("EMAIL_BACKEND") != "django.core.mail.backends.smtp.EmailBackend" or values.get("EMAIL_HOST") in {None, "", "localhost"} or not (values.get("EMAIL_USE_TLS") ^ values.get("EMAIL_USE_SSL")):
        errors.append("Configure SMTP with exactly one of TLS or SSL")
    sender = values.get("DEFAULT_FROM_EMAIL", "")
    try:
        validate_email(sender)
    except ValidationError:
        errors.append("Configure a valid production email sender")
    if sender.endswith("@oweru.example"):
        errors.append("Configure the verified production email sender")
    if errors:
        raise RuntimeError("Production configuration rejected: " + "; ".join(errors))
