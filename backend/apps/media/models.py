import posixpath
import secrets

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.contrib.gis.db import models as gis_models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import IntegrityError, models, transaction

from apps.common.models import TimeStampedModel


MEDIA_ID_RANDOM_HEX_LENGTH = 16
MEDIA_ID_MAX_COLLISION_RETRIES = 8


def generate_media_id():
    return f"MED-{secrets.token_hex(MEDIA_ID_RANDOM_HEX_LENGTH // 2).upper()}"


def normalize_file_key(value):
    value = (value or "").strip()
    if not value:
        raise ValidationError("File key is required.")
    lower_value = value.lower()
    if "://" in lower_value or lower_value.startswith("file:"):
        raise ValidationError("File key must be an opaque private storage key, not a URL.")
    if "\\" in value:
        raise ValidationError("File key must use normalized forward-slash object key separators.")
    if value.startswith("/"):
        raise ValidationError("File key must not be an absolute filesystem path.")
    if ".." in value.split("/"):
        raise ValidationError("File key must not contain path traversal.")

    normalized = posixpath.normpath(value)
    if normalized in {".", ""} or normalized.startswith("../") or normalized == "..":
        raise ValidationError("File key must not contain path traversal.")

    return normalized


def validate_file_key(value):
    normalize_file_key(value)


class Media(TimeStampedModel):
    class Source(models.TextChoices):
        UPLOAD = "UPLOAD", "Upload"
        CAMERA = "CAMERA", "Camera"
        SITE_CAPTURE = "SITE_CAPTURE", "Site capture"

    media_id = models.CharField(
        max_length=20,
        unique=True,
        default=generate_media_id,
        editable=False,
        db_index=True,
    )
    content_type = models.ForeignKey(ContentType, on_delete=models.PROTECT, related_name="media_items")
    object_id = models.UUIDField()
    owner = GenericForeignKey("content_type", "object_id")
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        related_name="uploaded_media",
    )
    file_key = models.CharField(max_length=1024, validators=[validate_file_key])
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.UPLOAD)
    captured_at = models.DateTimeField(null=True, blank=True)
    captured_location = gis_models.PointField(srid=4326, null=True, blank=True)
    device = models.CharField(max_length=255, blank=True)
    file_hash = models.CharField(max_length=128, blank=True)
    mime_type = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(size_bytes__gt=0), name="media_size_bytes_positive"),
        ]

    def __str__(self):
        return self.media_id

    def clean(self):
        super().clean()
        errors = {}

        try:
            self.file_key = normalize_file_key(self.file_key)
        except ValidationError as exc:
            errors["file_key"] = exc.messages

        if self.mime_type is not None:
            self.mime_type = self.mime_type.strip().lower()
            if not self.mime_type:
                errors["mime_type"] = "MIME type is required."

        if self.size_bytes is not None and self.size_bytes <= 0:
            errors["size_bytes"] = "Size in bytes must be greater than zero."

        if self.content_type_id and self.object_id and self.owner is None:
            errors["object_id"] = "Owner entity must exist."

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding or kwargs.get("force_update"):
            return super().save(*args, **kwargs)

        last_error = None
        for _ in range(MEDIA_ID_MAX_COLLISION_RETRIES):
            if not self.media_id:
                self.media_id = generate_media_id()
            if Media.objects.filter(media_id=self.media_id).exists():
                self.media_id = ""
                continue
            try:
                with transaction.atomic():
                    return super().save(*args, **kwargs)
            except IntegrityError as exc:
                last_error = exc
                self.media_id = ""

        if last_error:
            raise last_error
        raise IntegrityError("Could not generate a unique media_id.")


class MediaVariant(TimeStampedModel):
    class Kind(models.TextChoices):
        ORIGINAL = "ORIGINAL", "Original"
        DISPLAY = "DISPLAY", "Display"

    media = models.ForeignKey(Media, on_delete=models.CASCADE, related_name="variants")
    kind = models.CharField(max_length=20, choices=Kind.choices)
    file_key = models.CharField(max_length=1024, validators=[validate_file_key])
    mime_type = models.CharField(max_length=255)
    size_bytes = models.PositiveBigIntegerField(validators=[MinValueValidator(1)])
    width = models.PositiveIntegerField()
    height = models.PositiveIntegerField()

    class Meta:
        ordering = ["kind"]
        constraints = [
            models.UniqueConstraint(fields=["media", "kind"], name="media_variant_unique_kind"),
            models.CheckConstraint(condition=models.Q(size_bytes__gt=0), name="media_variant_size_bytes_positive"),
            models.CheckConstraint(condition=models.Q(width__gt=0), name="media_variant_width_positive"),
            models.CheckConstraint(condition=models.Q(height__gt=0), name="media_variant_height_positive"),
        ]

    def __str__(self):
        return f"{self.media.media_id}:{self.kind}"

    def clean(self):
        super().clean()
        errors = {}
        try:
            self.file_key = normalize_file_key(self.file_key)
        except ValidationError as exc:
            errors["file_key"] = exc.messages

        if self.mime_type is not None:
            self.mime_type = self.mime_type.strip().lower()
            if not self.mime_type:
                errors["mime_type"] = "MIME type is required."

        for field in ("size_bytes", "width", "height"):
            value = getattr(self, field)
            if value is not None and value <= 0:
                errors[field] = "Value must be greater than zero."

        if errors:
            raise ValidationError(errors)
