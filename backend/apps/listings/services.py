import secrets

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import IntegrityError, transaction
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.audit.services import create_audit_log
from apps.properties.models import PropertyRecord

from apps.lister_identity.models import ListerIdentity
from apps.lister_identity.services import is_lister_identity_verified

from .lifecycle import (
    ActivationRequirement,
    activation_eligibility_from_requirements,
    is_transition_documented,
)
from .audit_events import (
    LISTING_ACTIVATED,
    LISTING_CREATED,
    LISTING_RESTORED,
    LISTING_SUSPENDED,
    LISTING_UPDATED,
    LISTING_WITHDRAWN,
)
from .models import Listing
from . import policies


LISTING_ID_PREFIX = "LST"
LISTING_ID_TOKEN_BYTES = 8
LISTING_ID_MAX_ATTEMPTS = 8

LISTING_MUTABLE_FIELDS = frozenset({"selling_price", "owner_price", "description", "features"})
LISTING_SERVER_FIELDS = frozenset({
    "id",
    "listing_id",
    "property",
    "property_id",
    "lister",
    "lister_id",
    "lister_kind",
    "currency",
    "status",
    "created_at",
    "updated_at",
})
LISTING_UNSUPPORTED_FIELDS = frozenset({
    "owner_name",
    "owner_phone",
    "owner_whatsapp",
    "owner_bank_account",
    "phone_confirmed",
    "verification_level",
    "is_verified",
    "published_at",
    "promotion",
    "is_promoted",
    "photos",
    "media",
    "duplicate_status",
    "commission",
    "commission_rate",
    "lead",
    "deal",
    "transaction",
    "payment",
})


def _listing_id_token():
    return secrets.token_hex(LISTING_ID_TOKEN_BYTES).upper()


def generate_listing_id():
    for _ in range(LISTING_ID_MAX_ATTEMPTS):
        candidate = f"{LISTING_ID_PREFIX}-{_listing_id_token()}"
        if not Listing.objects.filter(listing_id=candidate).exists():
            return candidate
    raise ValidationError({"listing_id": "Could not generate a unique listing identifier."})


def _active_persisted_actor(actor):
    persisted = policies.get_active_persisted_actor(actor)
    if persisted is None:
        raise PermissionDenied("An active persisted account is required.")
    return persisted


def _ensure_can_create_listing(actor, lister_kind):
    if policies.role_code_for_lister_kind(lister_kind) is None:
        raise ValidationError({"lister_kind": "A valid lister kind is required."})
    if not policies.can_create_listing(actor, lister_kind=lister_kind):
        raise PermissionDenied("An active matching lister role is required.")


def _resolve_property_record(property_record):
    record_id = getattr(property_record, "pk", property_record)
    if not record_id:
        raise ValidationError({"property_record": "A persisted property record is required."})
    try:
        return PropertyRecord.objects.select_related("created_by").get(pk=record_id)
    except (TypeError, ValueError, DjangoValidationError, PropertyRecord.DoesNotExist) as exc:
        raise ValidationError({"property_record": "A valid property record is required."}) from exc


def _ensure_can_create_against_property(actor, property_record):
    if not policies.can_create_listing_for_property(actor, property_record):
        raise PermissionDenied("You cannot create a listing for this property record.")


def _clean_create_attrs(attrs):
    protected = LISTING_SERVER_FIELDS.intersection(attrs)
    if protected:
        raise ValidationError({field: "This field is server-controlled." for field in sorted(protected)})

    unsupported = (set(attrs) - LISTING_MUTABLE_FIELDS) | LISTING_UNSUPPORTED_FIELDS.intersection(attrs)
    if unsupported:
        raise ValidationError({field: "This field is not supported for listings." for field in sorted(unsupported)})

    return {field: attrs[field] for field in LISTING_MUTABLE_FIELDS if field in attrs}


def _clean_update_attrs(attrs):
    protected = LISTING_SERVER_FIELDS.intersection(attrs)
    if protected:
        raise ValidationError({field: "This field is immutable." for field in sorted(protected)})

    unsupported = (set(attrs) - LISTING_MUTABLE_FIELDS) | LISTING_UNSUPPORTED_FIELDS.intersection(attrs)
    if unsupported:
        raise ValidationError({field: "This field is not supported for listings." for field in sorted(unsupported)})

    return {field: attrs[field] for field in LISTING_MUTABLE_FIELDS if field in attrs}


def _validate_listing(listing):
    try:
        listing.full_clean()
    except DjangoValidationError as exc:
        raise ValidationError(exc.message_dict if hasattr(exc, "message_dict") else exc.messages) from exc


def _listing_field_value(listing, field):
    return getattr(listing, field)


def _effective_changed_fields(listing, values):
    return {field for field, value in values.items() if _listing_field_value(listing, field) != value}


def _listing_audit_identifiers(listing):
    return {
        "listing_id": listing.listing_id,
        "property_id": listing.property.property_id,
    }


def _listing_created_state(listing):
    return {
        **_listing_audit_identifiers(listing),
        "lister_kind": listing.lister_kind,
        "status": listing.status,
    }


def _listing_transition_state(listing, *, from_status, to_status, **extra):
    return {
        "listing_id": listing.listing_id,
        "from_status": from_status,
        "to_status": to_status,
        **extra,
    }


def _audit_listing(*, actor, action, listing, before=None, after=None, request=None):
    return create_audit_log(
        actor=actor,
        action=action,
        entity_type="Listing",
        entity_id=listing.pk,
        before=before or {},
        after=after or {},
        request=request,
    )


def _resolve_listing_for_update(listing):
    listing_pk = getattr(listing, "pk", listing)
    try:
        return Listing.objects.select_for_update().select_related("lister", "property").get(pk=listing_pk)
    except (TypeError, ValueError, DjangoValidationError, Listing.DoesNotExist) as exc:
        raise NotFound("Listing was not found.") from exc


def _ensure_can_update_listing(actor, listing):
    if not policies.can_update_listing(actor, listing):
        raise PermissionDenied("You cannot update this listing.")


def _ensure_can_activate_listing(actor, listing):
    if not policies.can_activate_listing(actor, listing):
        raise PermissionDenied("You cannot activate this listing.")


def _ensure_can_withdraw_listing(actor, listing):
    if not policies.can_withdraw_listing(actor, listing):
        raise PermissionDenied("You cannot withdraw this listing.")


def _ensure_can_suspend_listing(actor, listing):
    if not policies.can_suspend_listing(actor, listing):
        raise PermissionDenied("An active Management role is required.")


def _ensure_can_restore_listing(actor, listing):
    if not policies.can_restore_listing(actor, listing):
        raise PermissionDenied("An active Management role is required.")


def _ensure_documented_transition(listing, target_status):
    if not is_transition_documented(listing.status, target_status):
        raise ValidationError({"status": "This listing status transition is not allowed."})


def _set_listing_status(listing, target_status, *, actor, action, request=None, after_extra=None):
    from_status = listing.status
    listing.status = target_status
    _validate_listing(listing)
    listing.save(update_fields=["status", "updated_at"])
    _audit_listing(
        actor=actor,
        action=action,
        listing=listing,
        after=_listing_transition_state(
            listing,
            from_status=from_status,
            to_status=target_status,
            **(after_extra or {}),
        ),
        request=request,
    )
    return listing


def _verified_lister_identity_requirement(listing):
    try:
        identity = ListerIdentity.objects.select_related("user").get(user=listing.lister)
    except ListerIdentity.DoesNotExist:
        return ActivationRequirement("lister_identity_verified", "UNSATISFIED")
    status = "SATISFIED" if is_lister_identity_verified(identity) else "UNSATISFIED"
    return ActivationRequirement("lister_identity_verified", status)


def check_listing_activation_eligibility(*, listing):
    return activation_eligibility_from_requirements((
        _verified_lister_identity_requirement(listing),
        ActivationRequirement("lister_phone_confirmed", "UNAVAILABLE"),
        ActivationRequirement("listing_required_media", "UNAVAILABLE"),
    ))


def _ensure_activation_eligible(listing):
    eligibility = check_listing_activation_eligibility(listing=listing)
    if not eligibility.is_eligible:
        raise ValidationError({"activation": list(eligibility.blocked_codes)})
    return eligibility


@transaction.atomic
def create_listing(
    *,
    actor,
    property_record,
    lister_kind,
    selling_price,
    owner_price,
    description="",
    features=None,
    request=None,
    **attrs,
):
    actor = _active_persisted_actor(actor)
    _ensure_can_create_listing(actor, lister_kind)
    property_record = _resolve_property_record(property_record)
    _ensure_can_create_against_property(actor, property_record)

    values = _clean_create_attrs(attrs)
    values.update({
        "selling_price": selling_price,
        "owner_price": owner_price,
        "description": description,
        "features": [] if features is None else features,
    })

    for _ in range(LISTING_ID_MAX_ATTEMPTS):
        listing = Listing(
            listing_id=generate_listing_id(),
            property=property_record,
            lister=actor,
            lister_kind=lister_kind,
            currency=Listing.Currency.TZS,
            status=Listing.Status.DRAFT,
            **values,
        )
        _validate_listing(listing)
        try:
            with transaction.atomic():
                listing.save()
                _audit_listing(
                    actor=actor,
                    action=LISTING_CREATED,
                    listing=listing,
                    after=_listing_created_state(listing),
                    request=request,
                )
            return listing
        except IntegrityError as exc:
            if "listing_id" not in str(exc).lower():
                raise

    raise ValidationError({"listing_id": "Could not create a unique listing identifier."})


def get_listing(*, actor, listing_id):
    actor = _active_persisted_actor(actor)
    try:
        listing = Listing.objects.select_related("property", "lister").get(listing_id=listing_id)
    except Listing.DoesNotExist as exc:
        raise NotFound("Listing was not found.") from exc

    if policies.can_view_listing(actor, listing):
        return listing
    raise PermissionDenied("You do not have access to this listing.")


@transaction.atomic
def update_listing(*, actor, listing, request=None, **changes):
    actor = _active_persisted_actor(actor)
    values = _clean_update_attrs(changes)

    locked = _resolve_listing_for_update(listing)

    if locked.status != Listing.Status.DRAFT:
        raise PermissionDenied("Only draft listings can be updated.")
    _ensure_can_update_listing(actor, locked)

    changed_fields = _effective_changed_fields(locked, values)
    for field, value in values.items():
        setattr(locked, field, value)
    _validate_listing(locked)
    if changed_fields:
        locked.save(update_fields=[*changed_fields, "updated_at"])
        _audit_listing(
            actor=actor,
            action=LISTING_UPDATED,
            listing=locked,
            after={
                "listing_id": locked.listing_id,
                "changed_fields": sorted(changed_fields),
            },
            request=request,
        )
    return locked


@transaction.atomic
def activate_listing(*, actor, listing, request=None):
    actor = _active_persisted_actor(actor)
    locked = _resolve_listing_for_update(listing)
    _ensure_can_activate_listing(actor, locked)
    if locked.status == Listing.Status.SUSPENDED:
        raise PermissionDenied("Suspended listings require Management restoration.")
    _ensure_documented_transition(locked, Listing.Status.ACTIVE)
    _ensure_activation_eligible(locked)
    return _set_listing_status(locked, Listing.Status.ACTIVE, actor=actor, action=LISTING_ACTIVATED, request=request)


@transaction.atomic
def withdraw_listing(*, actor, listing, request=None):
    actor = _active_persisted_actor(actor)
    locked = _resolve_listing_for_update(listing)
    _ensure_can_withdraw_listing(actor, locked)
    _ensure_documented_transition(locked, Listing.Status.WITHDRAWN)
    return _set_listing_status(locked, Listing.Status.WITHDRAWN, actor=actor, action=LISTING_WITHDRAWN, request=request)


@transaction.atomic
def suspend_listing(*, actor, listing, reason, request=None):
    actor = _active_persisted_actor(actor)
    if reason is None or not isinstance(reason, str) or not reason.strip():
        raise ValidationError({"reason": "Suspension reason is required."})
    locked = _resolve_listing_for_update(listing)
    _ensure_can_suspend_listing(actor, locked)
    _ensure_documented_transition(locked, Listing.Status.SUSPENDED)
    return _set_listing_status(
        locked,
        Listing.Status.SUSPENDED,
        actor=actor,
        action=LISTING_SUSPENDED,
        request=request,
        after_extra={"reason_present": True},
    )


@transaction.atomic
def restore_listing(*, actor, listing, request=None):
    actor = _active_persisted_actor(actor)
    locked = _resolve_listing_for_update(listing)
    _ensure_can_restore_listing(actor, locked)
    _ensure_documented_transition(locked, Listing.Status.ACTIVE)
    _ensure_activation_eligible(locked)
    return _set_listing_status(locked, Listing.Status.ACTIVE, actor=actor, action=LISTING_RESTORED, request=request)


def get_accessible_listings(actor):
    return policies.get_accessible_listings(actor)
