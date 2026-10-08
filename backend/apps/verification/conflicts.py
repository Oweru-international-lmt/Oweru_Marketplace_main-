from apps.properties.policies import get_active_persisted_actor
from django.db.models import Q
from .models import PropertyRelationship


def has_property_conflict(user, property_record):
    actor = get_active_persisted_actor(user)
    if actor is None:
        return True
    if property_record.created_by_id == actor.pk:
        return True
    if property_record.listings.filter(lister=actor).exists():
        return True
    if property_record.listings.filter(owner_contact__whatsapp=actor.phone).exists():
        return True
    if property_record.verification_jobs.filter(Q(owner_user=actor) | Q(owner_phone=actor.phone)).exists():
        return True
    # An operational Professional account may belong to the same person as a
    # public lister account. Compare existing verified identity records privately.
    from apps.professionals.models import ProfessionalProfile
    profile = ProfessionalProfile.objects.filter(user=actor).first()
    if profile:
        from apps.lister_identity.models import ListerIdentity
        owner_ids = {property_record.created_by_id}
        owner_ids.update(property_record.listings.values_list("lister_id", flat=True))
        owner_ids.update(property_record.verification_jobs.exclude(owner_user_id=None).values_list("owner_user_id", flat=True))
        if ListerIdentity.objects.filter(user_id__in=owner_ids, status__in=["APPROVED", "EXPIRED"], national_id_number=profile.national_id_number).exists():
            return True
    return PropertyRelationship.objects.filter(property=property_record, user=actor).exists()
