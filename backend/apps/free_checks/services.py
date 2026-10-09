import hashlib
import re
from datetime import timedelta
from io import BytesIO
from xml.sax.saxutils import escape
from django.contrib.gis.measure import D
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from django.utils import timezone
from django.utils.module_loading import import_string
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError, Throttled
from apps.audit.services import create_audit_log
from apps.media.storage import get_private_media_storage
from apps.payments.documents import save_document, validate_document
from apps.payments.idempotency import Conflict, fingerprint
from apps.properties.models import PropertyRecord
from apps.properties.services import generate_property_id
from apps.site_capture.evidence import image_metadata
from apps.verification.configuration import setting
from apps.verification.task_services import private_write_scope
from .models import FreeCheck, FreeCheckPhoto, FreeCheckReport, FreeCheckLead
from .texts import TEXTS


def normalize_phone(value):
    number = re.sub(r"[\s()-]", "", value)
    if number.startswith("00"):
        number = "+" + number[2:]
    if re.fullmatch(r"0[67]\d{8}", number):
        number = "+255" + number[1:]
    if not re.fullmatch(r"\+[1-9]\d{7,14}", number):
        raise ValidationError("Use an international WhatsApp number.")
    return number


def lock_phone(phone):
    value = int.from_bytes(hashlib.sha256(phone.encode()).digest()[:8], "big", signed=True)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [value])


def distance(a, b):
    with connection.cursor() as cursor:
        cursor.execute("SELECT ST_Distance(ST_GeomFromEWKT(%s)::geography, ST_GeomFromEWKT(%s)::geography)", [a.ewkt, b.ewkt])
        return cursor.fetchone()[0]


def verdicts(pin, description, photos):
    # No rectangular bounding box is misrepresented as authoritative land data.
    provider_path = getattr(settings, "FREE_CHECK_GEOGRAPHY_PROVIDER", "")
    geo = import_string(provider_path)().check(pin=pin, description=description) if provider_path else {"land": "UNAVAILABLE", "description_match": "UNAVAILABLE"}
    if geo.get("land") not in {"LAND", "OUTSIDE", "UNAVAILABLE"} or geo.get("description_match") not in {"MATCH", "MISMATCH", "UNAVAILABLE"}:
        raise ValidationError("Invalid geography provider response.")
    nearby = PropertyRecord.objects.filter(pin__distance_lte=(pin, D(m=float(setting("duplicate_distance_m"))))).exists()
    locations = [location for _, location in photos if location is not None]
    photo_result = "MISMATCH" if any(distance(location, pin) > float(setting("photo_distance_m")) for location in locations) else "MATCH" if photos and len(locations) == len(photos) else "UNAVAILABLE"
    return {"land": geo["land"], "description_match": geo["description_match"], "duplicates": "FOUND" if nearby else "NONE", "photos": photo_result}


def token_for(check):
    # Deterministic, secret-key HMAC allows safe idempotent replay without storing bearer tokens.
    from django.utils.crypto import salted_hmac
    return salted_hmac("oweru.free-check", str(check.pk)).hexdigest()


def public_result(check):
    words = TEXTS[check.language]
    return {"id": str(check.pk), "reference": check.reference, "date": timezone.localtime(check.created_at).date(), "description": check.description, "category": check.property.category, "size": str(check.property.stated_size), "size_unit": check.property.size_unit, "verdicts": {key: {"status": value, "message": words[value]} for key, value in check.verdicts.items()}, "disclaimer": words["disclaimer"], "full_check": words["next"], "expires_at": check.expires_at}


def pdf_bytes(check):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    words = TEXTS[check.language]
    stream, story, styles = BytesIO(), [], getSampleStyleSheet()
    def add(value, style="BodyText"):
        story.extend([Paragraph(escape(str(value)), styles[style]), Spacer(1, 8)])
    add(words["title"], "Title")
    add(f"{words['reference']}: {check.reference}")
    add(f"{words['date']}: {timezone.localtime(check.created_at).date()}")
    add(f"{words['category']}: {check.property.category}")
    add(f"{words['size']}: {check.property.stated_size} {check.property.size_unit}")
    add(f"{words['description']}: {check.description}")
    for key, value in check.verdicts.items():
        add(f"{words[key]}: {words[value]}")
    add(words["disclaimer"], "Heading2")
    add(words["next"])
    SimpleDocTemplate(stream, pagesize=A4, leftMargin=45, rightMargin=45).build(story)
    return stream.getvalue()


def submit(*, values, key, photos=(), actor=None, request=None):
    from .api import CheckInput
    serializer = CheckInput(data=values)
    serializer.is_valid(raise_exception=True)
    data = serializer.validated_data
    phone = normalize_phone(data["phone"])
    if not isinstance(key, str) or not key.strip() or len(key) > 128:
        raise ValidationError("Idempotency-Key is required (maximum 128 characters).")
    if len(photos) > 5:
        raise ValidationError("At most five photos are allowed.")
    parsed = []
    for upload in photos:
        content, mime, digest = validate_document(upload)
        if mime not in {"image/jpeg", "image/png"}:
            raise ValidationError("Photos must be JPEG or PNG.")
        parsed.append((upload, image_metadata(content)[0]))
    digest = fingerprint({**data, "phone": phone, "pin": data["pin"].ewkt, "photos": [validate_document(p)[2] for p, _ in parsed]})
    with private_write_scope(), transaction.atomic():
        lock_phone(phone)
        old = FreeCheck.objects.filter(phone=phone, request_key=key).first()
        if old:
            if old.input_digest != digest:
                raise Conflict()
            if old.expires_at <= timezone.now():
                raise PermissionDenied("Report link expired.")
            return old
        day = timezone.localdate()
        if FreeCheck.objects.filter(phone=phone, created_at__date=day).count() >= int(setting("free_check_daily_limit")):
            raise Throttled(detail="Daily Free Check limit reached.")
        results = verdicts(data["pin"], data["description"], parsed)
        prop = PropertyRecord.objects.create(property_id=generate_property_id(), pin=data["pin"], category=data["category"], stated_size=data["size"], size_unit=data["size_unit"], title_type="UNKNOWN", is_outside_check=True, created_by=None)
        check = FreeCheck(property=prop, phone=phone, email=data.get("email", ""), language=data.get("language", "sw"), description=data["description"], external_url=data.get("external_url", ""), verdicts=results, expires_at=timezone.now() + timedelta(days=float(setting("free_check_report_days"))), request_key=key, input_digest=digest)
        check.token_digest = hashlib.sha256(token_for(check).encode()).hexdigest()
        check.save()
        FreeCheckLead.objects.create(free_check=check, user=actor if actor and actor.is_authenticated and actor.is_active else None)
        for upload, _ in parsed:
            FreeCheckPhoto.objects.create(free_check=check, media=save_document(actor=None, owner=check, upload=upload))
        media = save_document(actor=None, owner=check, upload=SimpleUploadedFile("free-check.pdf", pdf_bytes(check), content_type="application/pdf"))
        FreeCheckReport.objects.create(free_check=check, media=media)
        create_audit_log(action="free_check.completed", entity_type="FreeCheck", entity_id=check.pk, after={"reference": check.reference}, request=request)
        return check


def authorized_check(check_id, token, request=None):
    import secrets
    check = FreeCheck.objects.filter(pk=check_id).select_related("property").first()
    if check is None:
        raise NotFound()
    if not isinstance(token, str) or not secrets.compare_digest(check.token_digest, hashlib.sha256(token.encode()).hexdigest()) or check.expires_at <= timezone.now():
        raise PermissionDenied("Invalid or expired report link.")
    create_audit_log(action="sensitive_data.accessed", entity_type="FreeCheck", entity_id=check.pk, after={"purpose": "sanitized_report"}, request=request)
    return check

