import uuid
from datetime import datetime, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.lister_identity.models import ListerIdentity
from apps.lister_identity.services import (
    add_calendar_months,
    approve_lister_identity,
    create_lister_identity,
    expire_lister_identities,
    get_lister_identities_due_for_expiry_reminder,
    is_lister_identity_verified,
    reject_lister_identity,
    submit_lister_identity,
)
from apps.lister_identity.tasks import process_lister_identity_expiry
from apps.roles.catalog import ROLE_MANAGEMENT, ROLE_OWNER
from apps.roles.models import Role, UserRole
from apps.roles.services import bootstrap_canonical_roles


pytestmark = pytest.mark.django_db


def create_user():
    return get_user_model().objects.create_user(
        email=f"lifecycle-{uuid.uuid4().hex[:10]}@example.test",
        phone=f"+255{uuid.uuid4().int % 1000000000:09d}",
        full_name="Lifecycle User",
        password="StrongPass123!",
    )


def grant_role(user, role_code):
    bootstrap_canonical_roles()
    UserRole.objects.create(user=user, role=Role.objects.get(code=role_code), assigned_by=user)


def owner_user():
    user = create_user()
    grant_role(user, ROLE_OWNER)
    return user


def management_user():
    user = create_user()
    grant_role(user, ROLE_MANAGEMENT)
    return user


def submitted_identity(user=None):
    user = user or owner_user()
    identity = create_lister_identity(
        user=user,
        national_id_number="001234567890",
        national_id_photo_ref="private/id-photo",
        live_selfie_ref="private/selfie",
    )
    return submit_lister_identity(user=user, identity=identity)


def approved_identity(*, expires_at=None, reviewer=None):
    identity = submitted_identity()
    reviewer = reviewer or management_user()
    identity = approve_lister_identity(identity=identity, reviewed_by=reviewer)
    if expires_at is not None:
        identity.expires_at = expires_at
        identity.save(update_fields=["expires_at", "updated_at"])
    return identity


def test_calendar_month_addition_handles_month_end_and_leap_day():
    tz = timezone.get_current_timezone()

    assert add_calendar_months(datetime(2025, 1, 31, 10, tzinfo=tz), 1).date().isoformat() == "2025-02-28"
    assert add_calendar_months(datetime(2024, 2, 29, 10, tzinfo=tz), 12).date().isoformat() == "2025-02-28"


@override_settings(LISTER_IDENTITY_VALIDITY_MONTHS=2)
def test_approval_sets_expiry_from_review_time_using_configured_validity(monkeypatch):
    fixed_now = datetime(2026, 1, 31, 9, 30, tzinfo=timezone.get_current_timezone())
    monkeypatch.setattr("apps.lister_identity.services.timezone.now", lambda: fixed_now)
    identity = submitted_identity()

    reviewed = approve_lister_identity(identity=identity, reviewed_by=management_user())

    assert reviewed.reviewed_at == fixed_now
    assert reviewed.expires_at == datetime(2026, 3, 31, 9, 30, tzinfo=timezone.get_current_timezone())
    assert reviewed.submitted_at is not None


def test_rejection_leaves_expiry_null():
    reviewed = reject_lister_identity(identity=submitted_identity(), reviewed_by=management_user(), reason="Invalid")

    assert reviewed.status == ListerIdentity.Status.REJECTED
    assert reviewed.expires_at is None


def test_repeated_approval_does_not_recalculate_expiry(monkeypatch):
    first_now = datetime(2026, 1, 1, 9, tzinfo=timezone.get_current_timezone())
    second_now = datetime(2027, 1, 1, 9, tzinfo=timezone.get_current_timezone())
    monkeypatch.setattr("apps.lister_identity.services.timezone.now", lambda: first_now)
    identity = approve_lister_identity(identity=submitted_identity(), reviewed_by=management_user())
    original_expires_at = identity.expires_at
    monkeypatch.setattr("apps.lister_identity.services.timezone.now", lambda: second_now)

    with pytest.raises(ValidationError):
        approve_lister_identity(identity=identity, reviewed_by=management_user())

    identity.refresh_from_db()
    assert identity.expires_at == original_expires_at


def test_expiry_service_expires_due_identities_only_and_is_idempotent():
    now = timezone.now()
    reviewer = management_user()
    due = approved_identity(expires_at=now - timedelta(seconds=1), reviewer=reviewer)
    exact = approved_identity(expires_at=now, reviewer=reviewer)
    future = approved_identity(expires_at=now + timedelta(seconds=1), reviewer=reviewer)
    pending = submitted_identity()
    rejected = reject_lister_identity(identity=submitted_identity(), reviewed_by=reviewer, reason="No")
    expired = approved_identity(expires_at=now - timedelta(days=2), reviewer=reviewer)
    expired.status = ListerIdentity.Status.EXPIRED
    expired.save(update_fields=["status", "updated_at"])
    due_reviewed_at = due.reviewed_at
    due_reviewer = due.reviewed_by
    due_evidence = (due.national_id_number, due.national_id_photo_ref, due.live_selfie_ref)

    assert expire_lister_identities(at=now) == 2
    assert expire_lister_identities(at=now) == 0

    due.refresh_from_db()
    exact.refresh_from_db()
    future.refresh_from_db()
    pending.refresh_from_db()
    rejected.refresh_from_db()
    expired.refresh_from_db()
    assert due.status == ListerIdentity.Status.EXPIRED
    assert exact.status == ListerIdentity.Status.EXPIRED
    assert future.status == ListerIdentity.Status.APPROVED
    assert pending.status == ListerIdentity.Status.PENDING
    assert rejected.status == ListerIdentity.Status.REJECTED
    assert expired.status == ListerIdentity.Status.EXPIRED
    assert due.reviewed_at == due_reviewed_at
    assert due.reviewed_by == due_reviewer
    assert (due.national_id_number, due.national_id_photo_ref, due.live_selfie_ref) == due_evidence


def test_verification_predicate_requires_approved_future_expiry():
    now = timezone.now()
    assert is_lister_identity_verified(approved_identity(expires_at=now + timedelta(seconds=1)), at=now)
    assert not is_lister_identity_verified(approved_identity(expires_at=now), at=now)
    assert not is_lister_identity_verified(approved_identity(expires_at=now - timedelta(seconds=1)), at=now)

    null_expiry = approved_identity()
    null_expiry.expires_at = None
    null_expiry.save(update_fields=["expires_at", "updated_at"])
    assert not is_lister_identity_verified(null_expiry, at=now)
    assert not is_lister_identity_verified(submitted_identity(), at=now)
    assert not is_lister_identity_verified(
        reject_lister_identity(identity=submitted_identity(), reviewed_by=management_user(), reason="No"),
        at=now,
    )
    expired = approved_identity(expires_at=now + timedelta(days=1))
    expired.status = ListerIdentity.Status.EXPIRED
    expired.save(update_fields=["status", "updated_at"])
    assert not is_lister_identity_verified(expired, at=now)


@override_settings(LISTER_IDENTITY_EXPIRY_REMINDER_DAYS=30)
def test_expiry_reminder_foundation_returns_approved_identities_inside_window_only():
    now = timezone.now()
    due = approved_identity(expires_at=now + timedelta(days=30))
    outside = approved_identity(expires_at=now + timedelta(days=31))
    already_expired = approved_identity(expires_at=now - timedelta(seconds=1))
    pending = submitted_identity()
    rejected = reject_lister_identity(identity=submitted_identity(), reviewed_by=management_user(), reason="No")
    null_expiry = approved_identity()
    null_expiry.expires_at = None
    null_expiry.save(update_fields=["expires_at", "updated_at"])

    ids = set(get_lister_identities_due_for_expiry_reminder(at=now).values_list("pk", flat=True))

    assert due.pk in ids
    assert outside.pk not in ids
    assert already_expired.pk not in ids
    assert pending.pk not in ids
    assert rejected.pk not in ids
    assert null_expiry.pk not in ids


def test_expiry_task_delegates_to_service_and_is_repeat_safe(monkeypatch):
    calls = []

    def fake_expire():
        calls.append("called")
        return 3

    monkeypatch.setattr("apps.lister_identity.tasks.expire_lister_identities", fake_expire)

    assert process_lister_identity_expiry.run() == 3
    assert process_lister_identity_expiry.run() == 3
    assert calls == ["called", "called"]
