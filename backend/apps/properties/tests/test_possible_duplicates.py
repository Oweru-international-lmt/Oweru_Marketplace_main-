from decimal import Decimal
from io import BytesIO
import uuid

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from PIL import Image
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.models import AuditLog
from apps.listings.models import Listing
from apps.listings.services import check_listing_activation_eligibility, is_listing_media_ready
from apps.localities.models import District, Locality, Region, Ward
from apps.media.services import create_image_media
from apps.media.storage import reset_in_memory_storage
from apps.properties.audit_events import (
    PROPERTY_DUPLICATE_CONFIRMED,
    PROPERTY_DUPLICATE_DETECTED,
    PROPERTY_DUPLICATE_DISMISSED,
)
from apps.properties.duplicate_services import (
    confirm_possible_duplicate,
    dismiss_possible_duplicate,
    record_possible_duplicate,
)
from apps.properties.models import PossibleDuplicate, PropertyRecord
from apps.properties.services import create_property_record, update_property_record
from apps.roles.catalog import ROLE_AGENT, ROLE_MANAGEMENT, ROLE_OWNER, ROLE_VERIFIER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_settings(settings):
    settings.MEDIA_STORAGE_BACKEND = "memory"
    reset_in_memory_storage()
    yield
    reset_in_memory_storage()


def create_user(email=None, *, is_active=True):
    email = email or f"duplicate-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Duplicate User",
        password="StrongPass123!",
        is_active=is_active,
    )


def grant_role(user, role_code, *, is_active=True, role_active=True):
    bootstrap_canonical_roles()
    role = Role.objects.get(code=role_code)
    role.is_active = role_active
    role.save(update_fields=["is_active"])
    return UserRole.objects.create(user=user, role=role, is_active=is_active)


def hierarchy(prefix=None):
    prefix = prefix or f"Duplicate{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    return region, district, ward, locality


def property_attrs(prefix=None, **overrides):
    region, district, ward, locality = hierarchy(prefix)
    attrs = {
        "category": PropertyRecord.Category.LAND,
        "pin": Point(39.2083, -6.7924, srid=4326),
        "boundary": None,
        "region": region,
        "district": district,
        "ward": ward,
        "locality": locality,
        "stated_size": Decimal("1200.50"),
        "size_unit": "sqm",
        "title_type": PropertyRecord.TitleType.UNKNOWN,
    }
    attrs.update(overrides)
    return attrs


def direct_property(owner=None, prefix=None):
    owner = owner or create_user()
    attrs = property_attrs(prefix)
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        created_by=owner,
        **attrs,
    )


def listing(owner, prop=None):
    prop = prop or direct_property(owner)
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=prop,
        lister=owner,
        lister_kind=Listing.ListerKind.OWNER,
        selling_price=Decimal("100000000"),
        owner_price=Decimal("100000000"),
        currency=Listing.Currency.TZS,
        status=Listing.Status.DRAFT,
        description="Draft listing.",
        features=[],
    )


def image_upload():
    output = BytesIO()
    Image.new("RGB", (32, 24), color=(120, 80, 60)).save(output, format="JPEG")
    return SimpleUploadedFile("duplicate.jpg", output.getvalue(), content_type="image/jpeg")


def manager(*, is_active=True):
    user = create_user(is_active=is_active)
    grant_role(user, ROLE_MANAGEMENT)
    return user


def test_model_defaults_constraints_and_validation():
    first = direct_property(prefix="ModelA")
    second = direct_property(prefix="ModelB")
    candidate = PossibleDuplicate(property_a=second, property_b=first, signals=[
        PossibleDuplicate.SIGNAL_SIZE_SIMILARITY,
        PossibleDuplicate.SIGNAL_PIN_PROXIMITY,
        PossibleDuplicate.SIGNAL_SIZE_SIMILARITY,
    ])
    candidate.full_clean()
    candidate.save()

    assert candidate.status == PossibleDuplicate.Status.PENDING
    assert candidate.property_a_id == min(first.pk, second.pk)
    assert candidate.property_b_id == max(first.pk, second.pk)
    assert candidate.signals == [PossibleDuplicate.SIGNAL_PIN_PROXIMITY, PossibleDuplicate.SIGNAL_SIZE_SIMILARITY]

    with pytest.raises(DjangoValidationError):
        PossibleDuplicate(property_a=first, property_b=first, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY]).full_clean()
    with pytest.raises(DjangoValidationError):
        PossibleDuplicate(property_a=first, property_b=second, signals=["UNKNOWN"]).full_clean()
    with pytest.raises(DjangoValidationError):
        PossibleDuplicate(property_a=first, property_b=second, signals=[]).full_clean()
    with pytest.raises(DjangoValidationError):
        PossibleDuplicate(property_a=first, property_b=second, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY], distance_meters=-1).full_clean()
    with pytest.raises(DjangoValidationError):
        PossibleDuplicate(property_a=first, property_b=second, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY], size_difference_percent=-1).full_clean()


def test_database_prevents_unique_reversed_pair_and_self_pair():
    first = direct_property(prefix="UniqueA")
    second = direct_property(prefix="UniqueB")
    PossibleDuplicate.objects.create(property_a=first, property_b=second, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])

    with transaction.atomic(), pytest.raises(IntegrityError):
        PossibleDuplicate.objects.create(property_a=second, property_b=first, signals=[PossibleDuplicate.SIGNAL_SIZE_SIMILARITY])
    with transaction.atomic(), pytest.raises(IntegrityError):
        PossibleDuplicate.objects.create(property_a=first, property_b=first, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])


def test_duplicate_configuration_defaults_are_centralized():
    assert settings.PROPERTY_DUPLICATE_DISTANCE_METERS == 50
    assert settings.PROPERTY_DUPLICATE_SIZE_DIFFERENCE_PERCENT == 10


def test_record_service_creates_canonical_idempotent_candidate_and_merges_signals():
    first = direct_property(prefix="RecordA")
    second = direct_property(prefix="RecordB")

    candidate = record_possible_duplicate(
        property_a=second,
        property_b=first,
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
        distance_meters=Decimal("12.34"),
    )
    same = record_possible_duplicate(property_a=first, property_b=second, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])
    merged = record_possible_duplicate(
        property_a=second,
        property_b=first,
        signals=[PossibleDuplicate.SIGNAL_SIZE_SIMILARITY],
        size_difference_percent=Decimal("8.50"),
    )

    assert candidate.pk == same.pk == merged.pk
    assert PossibleDuplicate.objects.count() == 1
    assert merged.property_a_id == min(first.pk, second.pk)
    assert merged.property_b_id == max(first.pk, second.pk)
    assert merged.signals == [PossibleDuplicate.SIGNAL_PIN_PROXIMITY, PossibleDuplicate.SIGNAL_SIZE_SIMILARITY]
    assert merged.distance_meters == Decimal("12.34")
    assert merged.size_difference_percent == Decimal("8.50")
    assert AuditLog.objects.filter(action=PROPERTY_DUPLICATE_DETECTED).count() == 2


def test_record_service_rejects_invalid_inputs_and_does_not_mutate_properties():
    first = direct_property(prefix="InvalidA")
    second = direct_property(prefix="InvalidB")
    before = (first.property_id, second.property_id)

    with pytest.raises(ValidationError):
        record_possible_duplicate(property_a=first, property_b=first, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])
    with pytest.raises(ValidationError):
        record_possible_duplicate(property_a=PropertyRecord(), property_b=second, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])
    with pytest.raises(ValidationError):
        record_possible_duplicate(property_a=first, property_b=second, signals=["UNKNOWN"])
    with pytest.raises(ValidationError):
        record_possible_duplicate(property_a=first, property_b=second, signals=[])

    first.refresh_from_db()
    second.refresh_from_db()
    assert (first.property_id, second.property_id) == before


def test_reviewed_status_is_preserved_when_new_signal_arrives():
    first = direct_property(prefix="ReviewPreserveA")
    second = direct_property(prefix="ReviewPreserveB")
    candidate = record_possible_duplicate(property_a=first, property_b=second, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])
    dismiss_possible_duplicate(actor=manager(), possible_duplicate=candidate, review_note="distinct records")

    updated = record_possible_duplicate(property_a=second, property_b=first, signals=[PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY])

    assert updated.status == PossibleDuplicate.Status.NOT_DUPLICATE
    assert updated.reviewed_by_id is not None
    assert updated.reviewed_at is not None
    assert PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY in updated.signals


@pytest.mark.parametrize("role_code", [ROLE_OWNER, ROLE_AGENT, ROLE_VERIFIER])
def test_only_active_management_can_review(role_code):
    first = direct_property(prefix=f"Auth{role_code}A")
    second = direct_property(prefix=f"Auth{role_code}B")
    candidate = record_possible_duplicate(property_a=first, property_b=second, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])
    actor = create_user()
    grant_role(actor, role_code)

    with pytest.raises(PermissionDenied):
        confirm_possible_duplicate(actor=actor, possible_duplicate=candidate)


def test_inactive_revoked_and_fake_management_are_denied():
    candidate = record_possible_duplicate(
        property_a=direct_property(prefix="InactiveMgmtA"),
        property_b=direct_property(prefix="InactiveMgmtB"),
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
    )
    inactive = manager(is_active=False)
    with pytest.raises(PermissionDenied):
        confirm_possible_duplicate(actor=inactive, possible_duplicate=candidate)

    revoked = create_user()
    grant_role(revoked, ROLE_MANAGEMENT, is_active=False)
    with pytest.raises(PermissionDenied):
        confirm_possible_duplicate(actor=revoked, possible_duplicate=candidate)

    fake = create_user()
    fake.role = ROLE_MANAGEMENT
    fake.roles = [ROLE_MANAGEMENT]
    with pytest.raises(PermissionDenied):
        confirm_possible_duplicate(actor=fake, possible_duplicate=candidate)


def test_confirm_and_dismiss_review_lifecycle_and_no_merge_or_delete():
    first = direct_property(prefix="ConfirmA")
    second = direct_property(prefix="ConfirmB")
    candidate = record_possible_duplicate(property_a=first, property_b=second, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])
    reviewer = manager()

    confirmed = confirm_possible_duplicate(actor=reviewer, possible_duplicate=candidate, review_note=" same property ")
    assert confirmed.status == PossibleDuplicate.Status.CONFIRMED_DUPLICATE
    assert confirmed.reviewed_by == reviewer
    assert confirmed.reviewed_at is not None
    assert confirmed.review_note == "same property"
    with pytest.raises(ValidationError):
        confirm_possible_duplicate(actor=reviewer, possible_duplicate=confirmed)
    with pytest.raises(ValidationError):
        dismiss_possible_duplicate(actor=reviewer, possible_duplicate=confirmed)
    assert PropertyRecord.objects.filter(pk__in=[first.pk, second.pk]).count() == 2

    other = record_possible_duplicate(
        property_a=direct_property(prefix="DismissA"),
        property_b=direct_property(prefix="DismissB"),
        signals=[PossibleDuplicate.SIGNAL_SIZE_SIMILARITY],
    )
    dismissed = dismiss_possible_duplicate(actor=reviewer, possible_duplicate=other, review_note="not same")
    assert dismissed.status == PossibleDuplicate.Status.NOT_DUPLICATE


def test_audit_metadata_is_safe_and_audit_failure_rolls_back():
    first = direct_property(prefix="AuditA")
    second = direct_property(prefix="AuditB")
    candidate = record_possible_duplicate(property_a=first, property_b=second, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])
    confirm_possible_duplicate(actor=manager(), possible_duplicate=candidate, review_note="contains internal note")

    combined = " ".join(str(log.after) + str(log.before) for log in AuditLog.objects.filter(action__startswith="property.duplicate"))
    assert "Point" not in combined
    assert "boundary" not in combined.lower()
    assert "hash" not in combined.lower()
    assert "file_key" not in combined
    assert "signed" not in combined.lower()
    assert "internal note" not in combined

    rollback_a = direct_property(prefix="RollbackA")
    rollback_b = direct_property(prefix="RollbackB")
    with patch_create_audit_failure():
        with pytest.raises(RuntimeError):
            record_possible_duplicate(property_a=rollback_a, property_b=rollback_b, signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY])
    assert not PossibleDuplicate.objects.filter(property_a=rollback_a, property_b=rollback_b).exists()

    review = record_possible_duplicate(
        property_a=direct_property(prefix="ReviewRollbackA"),
        property_b=direct_property(prefix="ReviewRollbackB"),
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
    )
    with patch_create_audit_failure():
        with pytest.raises(RuntimeError):
            confirm_possible_duplicate(actor=manager(), possible_duplicate=review)
    review.refresh_from_db()
    assert review.status == PossibleDuplicate.Status.PENDING


class patch_create_audit_failure:
    def __enter__(self):
        self.patch = pytest.MonkeyPatch()
        import apps.properties.duplicate_services as duplicate_services

        def fail(*args, **kwargs):
            raise RuntimeError("audit failed")

        self.patch.setattr(duplicate_services, "create_audit_log", fail)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.patch.undo()


def test_hard_delete_policy_preserves_duplicate_history():
    candidate = record_possible_duplicate(
        property_a=direct_property(prefix="DeleteA"),
        property_b=direct_property(prefix="DeleteB"),
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
    )

    with pytest.raises(RuntimeError):
        candidate.delete()
    with pytest.raises(RuntimeError):
        PossibleDuplicate.objects.filter(pk=candidate.pk).delete()


def test_non_blocking_boundaries_remain_unchanged():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    created = create_property_record(actor=actor, **property_attrs(prefix="NonBlockingCreate"))
    updated = update_property_record(actor=actor, property_record=created, stated_size=Decimal("1300.00"))
    target_listing = listing(actor, prop=updated)
    create_image_media(actor=actor, owner_type="listing", owner_id=target_listing.listing_id, image=image_upload())

    record_possible_duplicate(
        property_a=updated,
        property_b=direct_property(prefix="NonBlockingOther"),
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
    )

    requirements = {item.code: item.status for item in check_listing_activation_eligibility(listing=target_listing).requirements}
    assert requirements["listing_required_media"] == "UNSATISFIED"
    assert is_listing_media_ready(target_listing) is False
    assert Listing.objects.filter(pk=target_listing.pk).exists()
    assert PropertyRecord.objects.filter(pk=updated.pk).exists()


def test_boundaries_no_http_api_detection_or_schema_changes():
    from django.urls import get_resolver
    from apps.listings.models import Listing
    from apps.media.models import Media

    paths = "".join(str(pattern.pattern) for pattern in get_resolver().url_patterns)
    assert "properties/duplicates/" not in paths
    assert "property-duplicates/" not in paths
    assert not hasattr(PropertyRecord, "merged_into")
    assert "PossibleDuplicate" not in {field.related_model.__name__ for field in Listing._meta.get_fields() if getattr(field, "related_model", None)}
    assert "PossibleDuplicate" not in {field.related_model.__name__ for field in Media._meta.get_fields() if getattr(field, "related_model", None)}
