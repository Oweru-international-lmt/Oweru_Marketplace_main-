from dataclasses import dataclass
from io import BytesIO
from secrets import token_urlsafe
from typing import BinaryIO, Protocol

from django.conf import settings


class PrivateMediaStorage(Protocol):
    def save_private_object(self, *, key: str, content: BinaryIO, content_type: str | None = None) -> str:
        """Persist private object content and return the canonical object key."""

    def generate_signed_read_url(self, *, key: str, expires_in: int | None = None) -> str:
        """Return a short-lived read URL for a private object."""

    def delete_private_object(self, *, key: str) -> None:
        """Delete a private object when a future lifecycle policy permits it."""

    def exists(self, *, key: str) -> bool:
        """Return whether the private object exists."""


@dataclass(frozen=True)
class MediaStorageConfig:
    backend: str
    bucket: str
    endpoint: str
    signed_url_ttl_seconds: int


def get_media_storage_config() -> MediaStorageConfig:
    return MediaStorageConfig(
        backend=settings.MEDIA_STORAGE_BACKEND,
        bucket=settings.MEDIA_STORAGE_BUCKET,
        endpoint=settings.MEDIA_STORAGE_ENDPOINT,
        signed_url_ttl_seconds=settings.MEDIA_SIGNED_URL_TTL_SECONDS,
    )


class UnconfiguredPrivateMediaStorage:
    def _raise_unconfigured(self):
        raise RuntimeError("Private media storage is not configured for object operations.")

    def save_private_object(self, *, key: str, content: BinaryIO, content_type: str | None = None) -> str:
        self._raise_unconfigured()

    def generate_signed_read_url(self, *, key: str, expires_in: int | None = None) -> str:
        self._raise_unconfigured()

    def delete_private_object(self, *, key: str) -> None:
        self._raise_unconfigured()

    def exists(self, *, key: str) -> bool:
        self._raise_unconfigured()


class InMemoryPrivateMediaStorage:
    def __init__(self):
        self.objects = {}
        self.deleted_keys = []
        self.signed_requests = []

    def save_private_object(self, *, key: str, content: BinaryIO, content_type: str | None = None) -> str:
        content.seek(0)
        self.objects[key] = {
            "bytes": content.read(),
            "content_type": content_type or "application/octet-stream",
        }
        return key

    def generate_signed_read_url(self, *, key: str, expires_in: int | None = None) -> str:
        if key not in self.objects:
            raise RuntimeError("Private media object does not exist.")
        ttl = expires_in or settings.MEDIA_SIGNED_URL_TTL_SECONDS
        token = token_urlsafe(24)
        self.signed_requests.append({"key": key, "expires_in": ttl, "token": token})
        return f"signed-media:{token}:ttl:{ttl}"

    def delete_private_object(self, *, key: str) -> None:
        self.deleted_keys.append(key)
        self.objects.pop(key, None)

    def exists(self, *, key: str) -> bool:
        return key in self.objects

    def read_private_object(self, *, key: str) -> BytesIO:
        return BytesIO(self.objects[key]["bytes"])


class S3PrivateMediaStorage:
    """S3-compatible adapter; credentials come from boto3's environment/provider chain."""
    def __init__(self, config):
        import boto3
        if not config.bucket:
            raise RuntimeError("MEDIA_STORAGE_BUCKET must be configured.")
        self.bucket = config.bucket
        self.ttl = config.signed_url_ttl_seconds
        self.client = boto3.client("s3", endpoint_url=config.endpoint or None)

    def save_private_object(self, *, key, content, content_type=None):
        content.seek(0)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=content, ContentType=content_type or "application/octet-stream")
        return key

    def generate_signed_read_url(self, *, key, expires_in=None):
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=expires_in or self.ttl)

    def delete_private_object(self, *, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, *, key):
        from botocore.exceptions import ClientError
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {"404", "NoSuchKey", "NotFound"}:
                return False
            raise


_in_memory_storage = InMemoryPrivateMediaStorage()


def reset_in_memory_storage():
    _in_memory_storage.objects.clear()
    _in_memory_storage.deleted_keys.clear()
    _in_memory_storage.signed_requests.clear()
    return _in_memory_storage


def get_private_media_storage() -> PrivateMediaStorage:
    config = get_media_storage_config()
    if config.backend == "unconfigured":
        return UnconfiguredPrivateMediaStorage()
    if config.backend in {"memory", "inmemory"}:
        return _in_memory_storage
    if config.backend == "s3":
        return S3PrivateMediaStorage(config)
    raise RuntimeError(f"Unsupported private media storage backend: {config.backend}")
