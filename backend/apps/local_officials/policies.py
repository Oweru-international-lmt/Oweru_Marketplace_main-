from apps.properties.models import PropertyRecord
from apps.verification.models import PropertyVerification

from .services import (
    get_effective_jurisdiction_assignments,
    get_effective_jurisdiction_assignments_covering_property,
)


def can_review_field_verification(user, verification, *, at=None):
    """Fail closed unless persisted local-official authority covers the property."""
    verification_id = getattr(verification, "pk", verification)
    try:
        field = (
            PropertyVerification.objects.select_related("property")
            .get(pk=verification_id, kind=PropertyVerification.Kind.FIELD)
        )
    except (TypeError, ValueError, PropertyVerification.DoesNotExist):
        return False
    from apps.verification.conflicts import has_property_conflict
    if has_property_conflict(user, field.property):
        return False
    return get_effective_jurisdiction_assignments_covering_property(
        user=user,
        property_record=field.property,
        at=at,
    ).exists()


def can_access_field_review_queue(user, *, at=None):
    """Require at least one current assignment before exposing a FIELD queue."""
    return get_effective_jurisdiction_assignments(user=user, at=at).exists()
