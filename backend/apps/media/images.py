import hashlib
import warnings
from dataclasses import dataclass
from io import BytesIO

from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework.exceptions import ValidationError


FORMAT_TO_MIME = {
    "JPEG": "image/jpeg",
    "PNG": "image/png",
    "WEBP": "image/webp",
}
MIME_TO_FORMAT = {value: key for key, value in FORMAT_TO_MIME.items()}


@dataclass(frozen=True)
class ProcessedImage:
    original_bytes: bytes
    display_bytes: bytes
    sha256: str
    mime_type: str
    original_width: int
    original_height: int
    display_width: int
    display_height: int


def _allowed_mime_types():
    return {mime.lower() for mime in settings.MEDIA_ALLOWED_IMAGE_MIME_TYPES}


def _read_upload(upload):
    if upload is None:
        raise ValidationError({"image": "Image upload is required."})

    try:
        size = upload.size
    except AttributeError:
        size = None
    if size == 0:
        raise ValidationError({"image": "Image upload must not be empty."})
    if size is not None and size > settings.MEDIA_MAX_UPLOAD_BYTES:
        raise ValidationError({"image": "Image upload exceeds the configured size limit."})

    try:
        upload.seek(0)
    except (AttributeError, OSError):
        pass
    data = upload.read()
    if not data:
        raise ValidationError({"image": "Image upload must not be empty."})
    if len(data) > settings.MEDIA_MAX_UPLOAD_BYTES:
        raise ValidationError({"image": "Image upload exceeds the configured size limit."})
    return data


def _decode_image(data):
    pixel_limit = max(settings.MEDIA_MAX_IMAGE_WIDTH * settings.MEDIA_MAX_IMAGE_HEIGHT * 4, 1)
    previous_limit = Image.MAX_IMAGE_PIXELS
    Image.MAX_IMAGE_PIXELS = pixel_limit
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                detected_format = image.format
                image.verify()
            with Image.open(BytesIO(data)) as image:
                if image.format != detected_format:
                    raise ValidationError({"image": "Image format is inconsistent."})
                loaded = ImageOps.exif_transpose(image)
                loaded.load()
                return loaded.copy(), detected_format
    except Image.DecompressionBombWarning as exc:
        raise ValidationError({"image": "Image dimensions exceed safe processing limits."}) from exc
    except (OSError, UnidentifiedImageError, ValueError) as exc:
        raise ValidationError({"image": "Uploaded file is not a valid supported image."}) from exc
    finally:
        Image.MAX_IMAGE_PIXELS = previous_limit


def _validate_mime(*, upload, actual_mime):
    allowed = _allowed_mime_types()
    if actual_mime not in allowed:
        raise ValidationError({"image": "Image format is not supported."})

    supplied_mime = (getattr(upload, "content_type", "") or "").lower()
    if supplied_mime:
        if supplied_mime not in allowed:
            raise ValidationError({"image": "Declared image MIME type is not supported."})
        if supplied_mime != actual_mime:
            raise ValidationError({"image": "Declared image MIME type does not match image content."})


def _resize_for_display(image):
    max_size = (settings.MEDIA_MAX_IMAGE_WIDTH, settings.MEDIA_MAX_IMAGE_HEIGHT)
    display = image.copy()
    display.thumbnail(max_size, Image.Resampling.LANCZOS)
    return display


def _save_display_image(image, mime_type):
    output = BytesIO()
    image_format = MIME_TO_FORMAT[mime_type]
    save_kwargs = {}
    if image_format == "JPEG":
        image = image.convert("RGB")
        save_kwargs.update({"quality": 82, "optimize": True, "progressive": True})
    elif image_format == "PNG":
        save_kwargs.update({"optimize": True})
    elif image_format == "WEBP":
        save_kwargs.update({"quality": 82, "method": 6})
    image.save(output, format=image_format, **save_kwargs)
    return output.getvalue()


def validate_and_process_image_upload(upload):
    data = _read_upload(upload)
    image, detected_format = _decode_image(data)
    actual_mime = FORMAT_TO_MIME.get(detected_format)
    if actual_mime is None:
        raise ValidationError({"image": "Image format is not supported."})
    _validate_mime(upload=upload, actual_mime=actual_mime)

    original_width, original_height = image.size
    if original_width <= 0 or original_height <= 0:
        raise ValidationError({"image": "Image dimensions are invalid."})

    display = _resize_for_display(image)
    display_bytes = _save_display_image(display, actual_mime)

    return ProcessedImage(
        original_bytes=data,
        display_bytes=display_bytes,
        sha256=hashlib.sha256(data).hexdigest(),
        mime_type=actual_mime,
        original_width=original_width,
        original_height=original_height,
        display_width=display.width,
        display_height=display.height,
    )
