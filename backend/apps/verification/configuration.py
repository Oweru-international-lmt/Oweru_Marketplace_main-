from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.conf import settings
from rest_framework.exceptions import PermissionDenied, ValidationError
from apps.leads.policies import authorize, management
from apps.audit.services import create_audit_log
from .models import VerificationSetting, SettingHistory
from apps.payments.idempotency import Conflict


DEFAULTS = {
    "identity_expiry_months": 12, "location_check_months": 6,
    "payout_working_days": 3, "official_registration_days": 14,
    "duplicate_distance_m": 50, "duplicate_size_percent": 10,
    "public_map_rounding_m": 200, "lost_sold_review_months": 6,
    "confirmation_days": 7,
    "email_max_attempts": 5, "outbox_waiting_hours": 2,
    "complaint_ack_working_days": 1, "complaint_payment_working_days": 5,
    "complaint_other_working_days": 10, "complaint_final_review_days": 14,
    "free_check_daily_limit": 5, "free_check_report_days": 30,
    "corner_accuracy_m": 10, "area_difference_percent": 10,
    "photo_distance_m": 200, "photo_age_days": 30,
    "professional_task_days": 7, "official_task_days": 14,
    "owner_consent_days": 7, "owner_contact_working_days": 3,
    "full_check_reliance_days": 30, "full_check_refresh_months": 6,
    "full_check_fee": None,
    "full_check_scope": "Owner consent, site capture, local office, applicable professional and Land Registry checks, verifier review and report.",
}

ENV_DEFAULTS = {
    "identity_expiry_months": "LISTER_IDENTITY_VALIDITY_MONTHS",
    "location_check_months": "PROPERTY_FIELD_VERIFICATION_VALIDITY_MONTHS",
    "payout_working_days": "PAYOUT_WORKING_DAYS",
    "duplicate_distance_m": "PROPERTY_DUPLICATE_DISTANCE_METERS",
    "duplicate_size_percent": "PROPERTY_DUPLICATE_SIZE_DIFFERENCE_PERCENT",
    "lost_sold_review_months": "LEAD_LOST_REVIEW_MONTHS",
    "confirmation_days": "OWNER_CONFIRMATION_DAYS",
}


def setting(key):
    row = VerificationSetting.objects.filter(key=key).first()
    return row.value if row else getattr(settings, ENV_DEFAULTS[key], DEFAULTS[key]) if key in ENV_DEFAULTS else DEFAULTS[key]


@transaction.atomic
def change_setting(*, actor, key, value, request=None, expected_version=None):
    actor = authorize(actor, "settings.manage")
    if not management(actor):
        raise ValidationError("Management is required.")
    if key not in DEFAULTS:
        raise ValidationError("Unknown verification setting.")
    if key == "full_check_fee" and actor.management_position != "DIRECTOR":
        raise PermissionDenied("The Full Check fee requires Director approval.")
    if key == "full_check_scope":
        if not isinstance(value, str) or not value.strip() or len(value) > 4000:
            raise ValidationError("A nonempty scope is required.")
    else:
        try:
            number = Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValidationError("A positive numeric value is required.") from exc
        if isinstance(value, bool) or not number.is_finite() or number <= 0 or number > (Decimal("999999999999999999") if key == "full_check_fee" else Decimal("1000000000")):
            raise ValidationError("A positive numeric value is required.")
        if key.endswith("days") or key.endswith("months") or key.endswith("limit") or key == "email_max_attempts" or key == "full_check_fee":
            if number != number.to_integral_value():
                raise ValidationError("Whole numbers are required.")
        value = str(number) if key == "full_check_fee" else float(number)
        if key.endswith("percent") and number > 100:
            raise ValidationError("Percentages cannot exceed 100.")
    from apps.free_checks.services import lock_phone
    lock_phone("setting:" + key)
    row = VerificationSetting.objects.select_for_update().filter(key=key).first()
    version = row.version if row else 0
    if expected_version is not None and expected_version != version:
        raise Conflict("Setting changed; refresh before editing.")
    before = row.value if row else setting(key)
    if row is None:
        row = VerificationSetting(key=key)
    row.value, row.changed_by = value, actor
    row.version = version + 1
    row.save()
    SettingHistory.objects.create(setting=row, actor=actor, version=row.version, value=value)
    create_audit_log(actor=actor, action="verification.setting_changed", entity_type="VerificationSetting", entity_id=row.pk, before={"value": before}, after={"key": key, "value": value, "version": row.version}, request=request)
    return row
