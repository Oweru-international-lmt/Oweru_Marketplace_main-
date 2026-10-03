import re

from rest_framework.exceptions import ValidationError


NATIONAL_ID_NUMBER_MAX_LENGTH = 100
EVIDENCE_REFERENCE_MAX_LENGTH = 500
EVIDENCE_REFERENCE_FIELDS = frozenset({"national_id_photo_ref", "live_selfie_ref"})

_BASE64_IMAGE_PREFIXES = ("/9j/", "ivborw0kggo", "r0lgod", "uklgr", "phn2zy")
_BASE64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


def normalize_national_id_number(value, *, required=False):
    if value is None:
        if required:
            raise ValidationError({"national_id_number": "National ID number is required."})
        return ""
    if not isinstance(value, str):
        raise ValidationError({"national_id_number": "National ID number must be a string."})

    normalized = value.strip()
    if required and not normalized:
        raise ValidationError({"national_id_number": "National ID number is required."})
    if len(normalized) > NATIONAL_ID_NUMBER_MAX_LENGTH:
        raise ValidationError({"national_id_number": "National ID number is too long."})
    return normalized


def _looks_like_embedded_base64_payload(value):
    compact = re.sub(r"\s+", "", value)
    lower = compact.lower()
    if lower.startswith(_BASE64_IMAGE_PREFIXES):
        return True
    return len(compact) >= 128 and bool(_BASE64_RE.fullmatch(compact)) and (
        "+" in compact or "/" in compact or compact.endswith("=")
    )


def normalize_evidence_reference(value, *, field_name):
    """Validate opaque private evidence refs, not media authenticity.

    Live-camera enforcement belongs at the future trusted media/capture
    boundary. This backend milestone only accepts already-minted opaque
    private evidence references.
    """
    if field_name not in EVIDENCE_REFERENCE_FIELDS:
        raise ValueError("Unknown lister identity evidence reference field.")
    if not isinstance(value, str):
        raise ValidationError({field_name: "Evidence reference must be a string."})

    normalized = value.strip()
    lowered = normalized.lower()
    if not normalized:
        raise ValidationError({field_name: "Evidence reference is required."})
    if len(normalized) > EVIDENCE_REFERENCE_MAX_LENGTH:
        raise ValidationError({field_name: "Evidence reference is too long."})
    if lowered.startswith(("http://", "https://", "data:", "file://")):
        raise ValidationError({field_name: "Evidence reference must be an opaque private reference."})
    if "../" in normalized or "..\\" in normalized:
        raise ValidationError({field_name: "Evidence reference must not contain filesystem traversal."})
    if normalized.startswith(("/", "~")) or _WINDOWS_ABSOLUTE_PATH_RE.match(normalized) or "\\" in normalized:
        raise ValidationError({field_name: "Evidence reference must not be a filesystem path."})
    if ";base64," in lowered or _looks_like_embedded_base64_payload(normalized):
        raise ValidationError({field_name: "Evidence reference must not contain embedded media data."})
    return normalized


def normalize_identity_evidence_attrs(attrs):
    normalized = {}
    if "national_id_number" in attrs:
        normalized["national_id_number"] = normalize_national_id_number(attrs["national_id_number"])
    for field in EVIDENCE_REFERENCE_FIELDS:
        if field in attrs:
            normalized[field] = normalize_evidence_reference(attrs[field], field_name=field)
    return normalized


def validate_submission_evidence(identity):
    return {
        "national_id_number": normalize_national_id_number(identity.national_id_number, required=True),
        "national_id_photo_ref": normalize_evidence_reference(
            identity.national_id_photo_ref,
            field_name="national_id_photo_ref",
        ),
        "live_selfie_ref": normalize_evidence_reference(identity.live_selfie_ref, field_name="live_selfie_ref"),
    }
