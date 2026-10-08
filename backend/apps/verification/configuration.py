from decimal import Decimal, InvalidOperation

from django.db import transaction
from rest_framework.exceptions import ValidationError
from apps.leads.policies import authorize, management
from apps.audit.services import create_audit_log
from .models import VerificationSetting


DEFAULTS = {
    "corner_accuracy_m": 10, "area_difference_percent": 10,
    "photo_distance_m": 200, "photo_age_days": 30,
    "professional_task_days": 7, "official_task_days": 14,
    "owner_consent_days": 7, "owner_contact_working_days": 3,
    "full_check_reliance_days": 30, "full_check_refresh_months": 6,
    "full_check_fee": None,
    "full_check_scope": "Owner consent, site capture, local office, applicable professional and Land Registry checks, verifier review and report.",
}


def setting(key):
    row = VerificationSetting.objects.filter(key=key).first()
    return row.value if row else DEFAULTS[key]


@transaction.atomic
def change_setting(*, actor, key, value, request=None):
    actor = authorize(actor, "settings.manage")
    if not management(actor):
        raise ValidationError("Management is required.")
    if key not in DEFAULTS:
        raise ValidationError("Unknown verification setting.")
    if key == "full_check_scope":
        if not isinstance(value, str) or not value.strip() or len(value) > 4000:
            raise ValidationError("A nonempty scope is required.")
    else:
        try:
            number = Decimal(str(value))
        except InvalidOperation as exc:
            raise ValidationError("A positive numeric value is required.") from exc
        if isinstance(value, bool) or not number.is_finite() or number <= 0:
            raise ValidationError("A positive numeric value is required.")
        if key.endswith("days") or key.endswith("months") or key == "full_check_fee":
            if number != number.to_integral_value():
                raise ValidationError("Whole numbers are required.")
        value = str(number) if key == "full_check_fee" else float(number)
    row, _ = VerificationSetting.objects.select_for_update().get_or_create(key=key, defaults={"value": value, "changed_by": actor})
    before = row.value
    row.value, row.changed_by = value, actor
    row.save()
    create_audit_log(actor=actor, action="verification.setting_changed", entity_type="VerificationSetting", entity_id=row.pk, before={"value": before}, after={"key": key, "value": value}, request=request)
    return row
