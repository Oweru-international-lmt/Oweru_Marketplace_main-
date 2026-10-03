from django.db import transaction

from .audit_events import ACCOUNT_DELETION_REQUESTED, record_account_event
from .models import AccountDeletionRequest


@transaction.atomic
def request_account_deletion(*, user, reason="", request=None):
    deletion_request, created = AccountDeletionRequest.objects.get_or_create(
        user=user,
        status=AccountDeletionRequest.Status.PENDING,
        defaults={"reason": (reason or "").strip()},
    )
    if created:
        record_account_event(
            action=ACCOUNT_DELETION_REQUESTED,
            user=user,
            entity_type="AccountDeletionRequest",
            entity_id=deletion_request.pk,
            after={"status": deletion_request.status, "reason_provided": bool(deletion_request.reason)},
            request=request,
        )
    return deletion_request
