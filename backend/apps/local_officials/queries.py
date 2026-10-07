from django.db.models import Exists, OuterRef

from apps.properties.models import PropertyRecord
from apps.verification.models import PropertyVerification

from .services import filter_property_queryset_by_effective_jurisdiction


def get_local_official_field_queue(*, user, at=None):
    """Return pending FIELD verifications covered by current jurisdiction."""
    eligible_properties = filter_property_queryset_by_effective_jurisdiction(
        PropertyRecord.objects.filter(pk=OuterRef("property_id")),
        user=user,
        at=at,
    )
    return (
        PropertyVerification.objects.select_related(
            "property__region",
            "property__district",
            "property__ward",
        )
        .filter(
            kind=PropertyVerification.Kind.FIELD,
            status=PropertyVerification.Status.PENDING,
        )
        .filter(Exists(eligible_properties))
        .order_by("submitted_at", "id")
    )
