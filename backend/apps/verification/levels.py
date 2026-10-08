"""Persist a cache of the authoritative live calculation, never a second ladder."""
from django.db import transaction
from django.utils import timezone
from apps.listings.models import Listing
from .models import VerificationLevelSnapshot
from .services import annotate_listing_queryset_with_effective_verification_level


@transaction.atomic
def recalculate_levels(*, property_id=None, user_id=None, listing_id=None, at=None):
    queryset = Listing.objects.all()
    if property_id is not None:
        queryset = queryset.filter(property_id=property_id)
    if user_id is not None:
        queryset = queryset.filter(lister_id=user_id)
    if listing_id is not None:
        queryset = queryset.filter(pk=listing_id)
    now = at or timezone.now()
    count = 0
    for listing_pk in queryset.values_list("pk", flat=True):
        snapshot, _ = VerificationLevelSnapshot.objects.get_or_create(listing_id=listing_pk, defaults={"level": 0, "calculated_at": now})
        snapshot = VerificationLevelSnapshot.objects.select_for_update().get(pk=snapshot.pk)
        # Compute after acquiring the cache lock so a concurrent event cannot write
        # a value calculated before the event whose cache update it waited for.
        row = annotate_listing_queryset_with_effective_verification_level(Listing.objects.filter(pk=listing_pk), at=now).only("pk").get()
        snapshot.level, snapshot.calculated_at = row.effective_verification_level, now
        snapshot.save(update_fields=["level", "calculated_at", "updated_at"])
        count += 1
    return count


def initialize_levels(sender, using="default", **kwargs):
    from django.db import connections
    if VerificationLevelSnapshot._meta.db_table in connections[using].introspection.table_names():
        recalculate_levels()
