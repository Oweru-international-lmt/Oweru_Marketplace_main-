from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
import uuid

import pytest
from django.contrib.auth import get_user_model
from django.contrib.gis.geos import Point
from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.test import override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.lister_identity.models import ListerIdentity
from apps.listings.audit_photo_events import LISTING_PHOTO_ADDED, LISTING_PHOTO_REMOVED, LISTING_PHOTOS_REORDERED
from apps.listings.models import Listing, ListingPhoto
from apps.listings.services import (
    LISTING_MINIMUM_PHOTOS,
    activate_listing,
    add_listing_photo,
    check_listing_activation_eligibility,
    is_listing_media_ready,
    remove_listing_photo,
    reorder_listing_photos,
)
from apps.localities.models import District, Locality, Region, Ward
from apps.media.models import Media, MediaVariant
from apps.media.services import create_image_media
from apps.media.storage import get_private_media_storage, reset_in_memory_storage
from apps.properties.audit_events import PROPERTY_DUPLICATE_DETECTED
from apps.properties.duplicate_services import (
    confirm_possible_duplicate,
    detect_photo_duplicates_for_listing_photo,
    dismiss_possible_duplicate,
    record_possible_duplicate,
)
from apps.properties.models import PossibleDuplicate, PropertyRecord
from apps.roles.catalog import ROLE_AGENT, ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def media_settings():
    reset_in_memory_storage()
    with override_settings(
        MEDIA_STORAGE_BACKEND="memory",
        MEDIA_MAX_UPLOAD_BYTES=1024 * 1024,
        MEDIA_ALLOWED_IMAGE_MIME_TYPES=["image/jpeg", "image/png", "image/webp"],
        MEDIA_MAX_IMAGE_WIDTH=80,
        MEDIA_MAX_IMAGE_HEIGHT=60,
        MEDIA_SIGNED_URL_TTL_SECONDS=123,
    ):
        yield
    reset_in_memory_storage()


def create_user(email=None, *, is_active=True):
    email = email or f"listing-photo-{uuid.uuid4().hex[:10]}@example.test"
    return get_user_model().objects.create_user(
        email=email,
        phone=f"+2557{abs(hash(email)) % 100000000:08d}",
        full_name="Listing Photo User",
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
    prefix = prefix or f"ListingPhoto{uuid.uuid4().hex[:8]}"
    region = Region.objects.create(name=f"{prefix} Region")
    district = District.objects.create(region=region, name=f"{prefix} District")
    ward = Ward.objects.create(district=district, name=f"{prefix} Ward")
    locality = Locality.objects.create(ward=ward, name=f"{prefix} Street", kind=Locality.Kind.STREET, approved=True)
    return region, district, ward, locality


def property_record(owner):
    region, district, ward, locality = hierarchy()
    return PropertyRecord.objects.create(
        property_id=f"OWR-{uuid.uuid4().hex[:16].upper()}",
        category=PropertyRecord.Category.LAND,
        pin=Point(39.2083, -6.7924, srid=4326),
        boundary=None,
        region=region,
        district=district,
        ward=ward,
        locality=locality,
        stated_size=Decimal("1200.50"),
        size_unit="sqm",
        title_type=PropertyRecord.TitleType.UNKNOWN,
        created_by=owner,
    )


def listing(owner, *, lister_kind=Listing.ListerKind.OWNER, status=Listing.Status.DRAFT, prop=None):
    prop = prop or property_record(owner)
    selling = Decimal("100000000")
    owner_price = selling if lister_kind == Listing.ListerKind.OWNER else Decimal("90000000")
    return Listing.objects.create(
        listing_id=f"LST-{uuid.uuid4().hex[:16].upper()}",
        property=prop,
        lister=owner,
        lister_kind=lister_kind,
        selling_price=selling,
        owner_price=owner_price,
        currency=Listing.Currency.TZS,
        status=status,
        description="Draft listing.",
        features=[],
    )


def image_upload(color=(130, 100, 90)):
    output = BytesIO()
    Image.new("RGB", (32, 24), color=color).save(output, format="JPEG")
    return SimpleUploadedFile(f"client-{uuid.uuid4().hex}.jpg", output.getvalue(), content_type="image/jpeg")


def listing_media(actor, target_listing, *, color=(130, 100, 90)):
    return create_image_media(actor=actor, owner_type="listing", owner_id=target_listing.listing_id, image=image_upload(color=color))


def property_media(actor, target_property):
    return create_image_media(actor=actor, owner_type="property_record", owner_id=target_property.property_id, image=image_upload())


def identity_for(user):
    return ListerIdentity.objects.create(
        user=user,
        national_id_number=f"NIDA-{uuid.uuid4().hex[:12]}",
        national_id_photo_ref="identity/photo.jpg",
        live_selfie_ref="identity/selfie.jpg",
        status=ListerIdentity.Status.APPROVED,
        reviewed_at=timezone.now(),
        expires_at=timezone.now() + timezone.timedelta(days=30),
    )


def duplicate_between(first, second):
    return PossibleDuplicate.objects.get(
        Q(property_a=first, property_b=second) | Q(property_a=second, property_b=first)
    )


def matching_photo_pair(actor, *, first_listing=None, second_listing=None, color=(130, 100, 90)):
    first_listing = first_listing or listing(actor)
    second_listing = second_listing or listing(actor)
    first_photo = add_listing_photo(actor=actor, listing=first_listing, media=listing_media(actor, first_listing, color=color))
    second_photo = add_listing_photo(actor=actor, listing=second_listing, media=listing_media(actor, second_listing, color=color))
    return first_listing, second_listing, first_photo, second_photo


def test_listing_photo_model_constraints_and_validation():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)
    media = listing_media(actor, target)
    photo = ListingPhoto.objects.create(listing=target, media=media, position=0)

    assert photo.listing == target
    assert photo.media == media

    with transaction.atomic(), pytest.raises(IntegrityError):
        ListingPhoto.objects.create(listing=target, media=media, position=1)
    with transaction.atomic(), pytest.raises(IntegrityError):
        ListingPhoto.objects.create(listing=target, media=listing_media(actor, target), position=0)

    invalid = ListingPhoto(listing=target, media=listing_media(actor, target), position=-1)
    with pytest.raises(DjangoValidationError):
        invalid.full_clean()


def test_exact_listing_owned_media_is_required():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    first = listing(actor)
    second = listing(actor)

    add_listing_photo(actor=actor, listing=first, media=listing_media(actor, first))
    with pytest.raises(ValidationError):
        add_listing_photo(actor=actor, listing=first, media=listing_media(actor, second))
    with pytest.raises(ValidationError):
        add_listing_photo(actor=actor, listing=first, media=property_media(actor, first.property))


def test_unrelated_inactive_revoked_and_fake_role_users_are_denied():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)
    media = listing_media(actor, target)

    unrelated = create_user()
    grant_role(unrelated, ROLE_OWNER)
    with pytest.raises(PermissionDenied):
        add_listing_photo(actor=unrelated, listing=target, media=media)

    actor.is_active = False
    actor.save(update_fields=["is_active"])
    with pytest.raises(PermissionDenied):
        add_listing_photo(actor=actor, listing=target, media=media)
    actor.is_active = True
    actor.save(update_fields=["is_active"])
    UserRole.objects.filter(user=actor, role__code=ROLE_OWNER).update(is_active=False)
    with pytest.raises(PermissionDenied):
        add_listing_photo(actor=actor, listing=target, media=media)

    fake = create_user()
    fake.role = ROLE_OWNER
    fake.roles = [ROLE_OWNER]
    with pytest.raises(PermissionDenied):
        add_listing_photo(actor=fake, listing=target, media=media)


def test_add_append_explicit_remove_and_media_lifecycle_boundary():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)
    first_media = listing_media(actor, target)
    second_media = listing_media(actor, target)
    storage = get_private_media_storage()
    original_key_count = len(storage.objects)

    first = add_listing_photo(actor=actor, listing=target, media=first_media)
    second = add_listing_photo(actor=actor, listing=target, media=second_media, position=5)

    assert first.position == 0
    assert second.position == 5

    remove_listing_photo(actor=actor, listing=target, listing_photo=first)

    assert not ListingPhoto.objects.filter(pk=first.pk).exists()
    assert Media.objects.filter(pk=first_media.pk).exists()
    assert MediaVariant.objects.filter(media=first_media).count() == 2
    assert len(storage.objects) == original_key_count


def test_reorder_success_and_invalid_reorders_roll_back():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)
    photos = [add_listing_photo(actor=actor, listing=target, media=listing_media(actor, target)) for _ in range(3)]

    reordered = reorder_listing_photos(actor=actor, listing=target, ordered_photo_ids=[photos[2].pk, photos[0].pk, photos[1].pk])
    assert [photo.pk for photo in reordered] == [photos[2].pk, photos[0].pk, photos[1].pk]
    assert list(ListingPhoto.objects.filter(listing=target).order_by("position").values_list("position", flat=True)) == [0, 1, 2]

    before = list(ListingPhoto.objects.filter(listing=target).order_by("position").values_list("pk", flat=True))
    with pytest.raises(ValidationError):
        reorder_listing_photos(actor=actor, listing=target, ordered_photo_ids=[photos[0].pk])
    with pytest.raises(ValidationError):
        reorder_listing_photos(actor=actor, listing=target, ordered_photo_ids=[photos[0].pk, photos[0].pk, photos[1].pk])

    other = listing(actor)
    other_photo = add_listing_photo(actor=actor, listing=other, media=listing_media(actor, other))
    with pytest.raises(ValidationError):
        reorder_listing_photos(actor=actor, listing=target, ordered_photo_ids=[photos[0].pk, photos[1].pk, other_photo.pk])
    assert list(ListingPhoto.objects.filter(listing=target).order_by("position").values_list("pk", flat=True)) == before


@pytest.mark.parametrize("count,expected", [(0, False), (1, False), (2, False), (3, True), (4, True)])
def test_listing_media_readiness_counts_valid_photos(count, expected):
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)

    for _ in range(count):
        add_listing_photo(actor=actor, listing=target, media=listing_media(actor, target))

    assert is_listing_media_ready(target) is expected
    assert LISTING_MINIMUM_PHOTOS == 3


def test_readiness_ignores_missing_variants_and_wrong_owner_associations():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)
    wrong_owner = listing(actor)

    valid_media = [listing_media(actor, target) for _ in range(2)]
    for media in valid_media:
        add_listing_photo(actor=actor, listing=target, media=media)

    no_display = listing_media(actor, target)
    no_display.variants.filter(kind=MediaVariant.Kind.DISPLAY).delete()
    ListingPhoto.objects.create(listing=target, media=no_display, position=2)

    wrong_media = listing_media(actor, wrong_owner)
    ListingPhoto.objects.create(listing=target, media=wrong_media, position=3)

    assert is_listing_media_ready(target) is False


def test_activation_media_requirement_distinguishes_photo_readiness_and_phone_boundary():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)
    identity_for(actor)

    requirements = {item.code: item.status for item in check_listing_activation_eligibility(listing=target).requirements}
    assert requirements["listing_required_media"] == "UNSATISFIED"
    assert requirements["lister_phone_confirmed"] == "UNAVAILABLE"

    for _ in range(3):
        add_listing_photo(actor=actor, listing=target, media=listing_media(actor, target))

    requirements = {item.code: item.status for item in check_listing_activation_eligibility(listing=target).requirements}
    assert requirements["lister_identity_verified"] == "SATISFIED"
    assert requirements["listing_required_media"] == "SATISFIED"
    assert requirements["lister_phone_confirmed"] == "UNAVAILABLE"
    with pytest.raises(ValidationError) as exc:
        activate_listing(actor=actor, listing=target)
    assert "lister_phone_confirmed" in exc.value.detail["activation"]


def test_listing_photo_api_private_and_safe_response_fields():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)
    media = listing_media(actor, target)
    client = APIClient()

    assert client.get(f"/api/v1/listings/{target.listing_id}/photos/").status_code == 401
    client.force_authenticate(actor)
    response = client.post(f"/api/v1/listings/{target.listing_id}/photos/", {"media_id": media.media_id}, format="json")
    assert response.status_code == 201
    payload = response.json()
    assert set(payload) == {"id", "media_id", "position", "created_at"}
    assert "file_key" not in str(payload)
    assert "hash" not in str(payload).lower()
    assert "gps" not in str(payload).lower()

    listed = client.get(f"/api/v1/listings/{target.listing_id}/photos/")
    assert listed.status_code == 200
    assert listed.json()[0]["media_id"] == media.media_id

    assert client.post(f"/api/v1/listings/{target.listing_id}/photos/", {"media_id": "MED-NOTFOUND"}, format="json").status_code == 400

    reorder = client.post(
        f"/api/v1/listings/{target.listing_id}/photos/reorder/",
        {"photo_ids": [payload["id"]]},
        format="json",
    )
    assert reorder.status_code == 200

    delete_response = client.delete(f"/api/v1/listings/{target.listing_id}/photos/{payload['id']}/")
    assert delete_response.status_code == 204
    assert Media.objects.filter(pk=media.pk).exists()


def test_listing_photo_api_denies_unrelated_user():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)
    media = listing_media(actor, target)
    unrelated = create_user()
    grant_role(unrelated, ROLE_OWNER)
    client = APIClient()
    client.force_authenticate(unrelated)

    response = client.post(f"/api/v1/listings/{target.listing_id}/photos/", {"media_id": media.media_id}, format="json")

    assert response.status_code == 403


def test_listing_photo_audit_and_failure_rollback_are_safe():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)
    photo = add_listing_photo(actor=actor, listing=target, media=listing_media(actor, target))
    reorder_listing_photos(actor=actor, listing=target, ordered_photo_ids=[photo.pk])
    remove_listing_photo(actor=actor, listing=target, listing_photo=photo)

    assert AuditLog.objects.filter(action=LISTING_PHOTO_ADDED).count() == 1
    assert AuditLog.objects.filter(action=LISTING_PHOTOS_REORDERED).count() == 1
    assert AuditLog.objects.filter(action=LISTING_PHOTO_REMOVED).count() == 1
    combined = " ".join(str(log.after) + str(log.before) for log in AuditLog.objects.filter(action__startswith="listing.photo"))
    assert "file_key" not in combined
    assert "hash" not in combined.lower()
    assert "signed" not in combined.lower()
    assert "gps" not in combined.lower()

    media = listing_media(actor, target)
    with patch("apps.listings.services.create_audit_log", side_effect=RuntimeError("audit failed")):
        with pytest.raises(RuntimeError):
            add_listing_photo(actor=actor, listing=target, media=media)
    assert not ListingPhoto.objects.filter(media=media).exists()


def test_identical_listing_photo_hashes_create_photo_similarity_duplicate():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    first, second, _, _ = matching_photo_pair(actor)

    candidate = duplicate_between(first.property, second.property)

    assert candidate.signals == [PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY]
    assert AuditLog.objects.filter(action=PROPERTY_DUPLICATE_DETECTED).count() == 1


def test_different_listing_photo_hashes_do_not_create_photo_similarity():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    first = listing(actor)
    second = listing(actor)

    add_listing_photo(actor=actor, listing=first, media=listing_media(actor, first, color=(10, 20, 30)))
    add_listing_photo(actor=actor, listing=second, media=listing_media(actor, second, color=(30, 20, 10)))

    assert not PossibleDuplicate.objects.exists()


def test_same_property_across_multiple_listings_does_not_self_flag():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    prop = property_record(actor)
    first = listing(actor, prop=prop)
    second = listing(actor, prop=prop)

    add_listing_photo(actor=actor, listing=first, media=listing_media(actor, first))
    add_listing_photo(actor=actor, listing=second, media=listing_media(actor, second))

    assert not PossibleDuplicate.objects.exists()


def test_multiple_matching_photos_between_same_properties_create_one_pair():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    first = listing(actor)
    second = listing(actor)

    matching_photo_pair(actor, first_listing=first, second_listing=second, color=(100, 90, 80))
    matching_photo_pair(actor, first_listing=first, second_listing=second, color=(80, 90, 100))

    candidate = duplicate_between(first.property, second.property)
    assert PossibleDuplicate.objects.count() == 1
    assert candidate.signals == [PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY]


@pytest.mark.parametrize("existing_signal", [PossibleDuplicate.SIGNAL_PIN_PROXIMITY, PossibleDuplicate.SIGNAL_SIZE_SIMILARITY])
def test_photo_similarity_merges_with_existing_duplicate_signals(existing_signal):
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    first = listing(actor)
    second = listing(actor)
    record_possible_duplicate(property_a=first.property, property_b=second.property, signals=[existing_signal])

    matching_photo_pair(actor, first_listing=first, second_listing=second)

    candidate = duplicate_between(first.property, second.property)
    assert candidate.signals == sorted([existing_signal, PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY])
    assert PossibleDuplicate.objects.count() == 1


def test_photo_similarity_is_idempotent_and_canonical_for_reversed_detection():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    first, second, first_photo, second_photo = matching_photo_pair(actor)

    detect_photo_duplicates_for_listing_photo(listing_photo=first_photo)
    detect_photo_duplicates_for_listing_photo(listing_photo=second_photo)

    candidate = duplicate_between(first.property, second.property)
    assert PossibleDuplicate.objects.count() == 1
    assert candidate.signals == [PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY]


@pytest.mark.parametrize("review", ["confirmed", "dismissed"])
def test_review_state_survives_later_photo_similarity(review):
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    reviewer = create_user()
    grant_role(reviewer, ROLE_MANAGEMENT)
    first = listing(actor)
    second = listing(actor)
    candidate = record_possible_duplicate(
        property_a=first.property,
        property_b=second.property,
        signals=[PossibleDuplicate.SIGNAL_PIN_PROXIMITY],
    )
    if review == "confirmed":
        reviewed = confirm_possible_duplicate(actor=reviewer, possible_duplicate=candidate, review_note="same")
        expected_status = PossibleDuplicate.Status.CONFIRMED_DUPLICATE
    else:
        reviewed = dismiss_possible_duplicate(actor=reviewer, possible_duplicate=candidate, review_note="distinct")
        expected_status = PossibleDuplicate.Status.NOT_DUPLICATE

    matching_photo_pair(actor, first_listing=first, second_listing=second)

    reviewed.refresh_from_db()
    assert reviewed.status == expected_status
    assert reviewed.reviewed_by == reviewer
    assert reviewed.reviewed_at is not None
    assert PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY in reviewed.signals


@pytest.mark.parametrize("file_hash", ["", "not-a-sha256", "g" * 64])
def test_blank_or_invalid_hash_fails_safely(file_hash):
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    first = listing(actor)
    second = listing(actor)
    first_photo = add_listing_photo(actor=actor, listing=first, media=listing_media(actor, first))
    second_media = listing_media(actor, second)
    second_media.file_hash = file_hash
    second_media.save(update_fields=["file_hash", "updated_at"])

    add_listing_photo(actor=actor, listing=second, media=second_media)
    assert detect_photo_duplicates_for_listing_photo(listing_photo=first_photo) == []
    assert not PossibleDuplicate.objects.exists()


def test_photo_hash_is_not_exposed_in_api_or_duplicate_audit_metadata():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    first, second, _, _ = matching_photo_pair(actor)
    client = APIClient()
    client.force_authenticate(actor)

    response = client.get(f"/api/v1/listings/{second.listing_id}/photos/")
    payload = response.json()
    candidate = duplicate_between(first.property, second.property)
    duplicate_audit = AuditLog.objects.filter(action=PROPERTY_DUPLICATE_DETECTED).latest("created_at")
    combined = f"{payload} {duplicate_audit.before} {duplicate_audit.after}"

    assert response.status_code == 200
    assert "hash" not in combined.lower()
    assert second.photos.first().media.file_hash not in combined
    assert PossibleDuplicate.SIGNAL_PHOTO_SIMILARITY in candidate.signals


def test_invalid_listing_photo_association_cannot_create_arbitrary_duplicate():
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    first = listing(actor)
    second = listing(actor)
    wrong_media = listing_media(actor, second)
    invalid_photo = ListingPhoto.objects.create(listing=first, media=wrong_media, position=0)

    assert detect_photo_duplicates_for_listing_photo(listing_photo=invalid_photo) == []
    assert not PossibleDuplicate.objects.exists()


def test_add_listing_photo_triggers_advisory_photo_detection(monkeypatch):
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)
    calls = []

    def fake_detector(*, listing_photo, request=None):
        calls.append(listing_photo.pk)
        return []

    monkeypatch.setattr("apps.listings.services.detect_photo_duplicates_for_listing_photo", fake_detector)
    photo = add_listing_photo(actor=actor, listing=target, media=listing_media(actor, target))

    assert calls == [photo.pk]


def test_recoverable_photo_duplicate_detection_failure_keeps_photo_association(monkeypatch):
    actor = create_user()
    grant_role(actor, ROLE_OWNER)
    target = listing(actor)

    def failing_detector(*, listing_photo, request=None):
        raise ValidationError({"photo_duplicate_detection": "temporary issue"})

    monkeypatch.setattr("apps.listings.services.detect_photo_duplicates_for_listing_photo", failing_detector)
    photo = add_listing_photo(actor=actor, listing=target, media=listing_media(actor, target))

    assert ListingPhoto.objects.filter(pk=photo.pk).exists()


def test_boundaries_no_duplicate_public_gallery_or_domain_schema_changes():
    assert not hasattr(PropertyRecord, "possible_duplicates")
    assert "national_id_photo_ref" in {field.name for field in ListerIdentity._meta.get_fields()}
    assert "live_selfie_ref" in {field.name for field in ListerIdentity._meta.get_fields()}
