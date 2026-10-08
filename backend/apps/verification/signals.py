from django.db.models.signals import post_save
from django.dispatch import receiver
from apps.listings.models import Listing
from apps.lister_identity.models import ListerIdentity
from .models import PropertyVerification, VerificationJob
from .levels import recalculate_levels


@receiver(post_save, sender=Listing, dispatch_uid="verification.listing_level")
def listing_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        recalculate_levels(listing_id=instance.pk)


@receiver(post_save, sender=ListerIdentity, dispatch_uid="verification.identity_level")
def identity_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        recalculate_levels(user_id=instance.user_id)


@receiver(post_save, sender=PropertyVerification, dispatch_uid="verification.property_level")
@receiver(post_save, sender=VerificationJob, dispatch_uid="verification.full_check_level")
def property_check_changed(sender, instance, raw=False, **kwargs):
    if not raw:
        recalculate_levels(property_id=instance.property_id)
