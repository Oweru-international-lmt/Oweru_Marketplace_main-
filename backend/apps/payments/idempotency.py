import hashlib
import json
from django.db import transaction
from rest_framework.exceptions import APIException, ValidationError
from .models import IdempotencyRecord


class Conflict(APIException):
    status_code = 409
    default_detail = "Idempotency key was used for a different logical request."


def fingerprint(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True, default=str).encode()).hexdigest()


@transaction.atomic
def execute(*, actor_scope, operation, resource, key, payload, lock, authorize, mutation):
    """Lock a stable resource BEFORE claiming. Rollback removes claim and result.

    All callers use the same Deal lock for financial workflows. External owner
    tokens use a delivery scope, never an unauthenticated shared actor bucket.
    Authorization runs before both mutation and replay.
    """
    if not isinstance(key, str) or not key.strip() or len(key) > 128:
        raise ValidationError({"Idempotency-Key": "A nonempty key of at most 128 characters is required."})
    locked = lock()
    authorize(locked)
    scope = dict(actor_scope=str(actor_scope), operation=operation, resource=resource, key=key)
    digest = fingerprint(payload)
    record = IdempotencyRecord.objects.select_for_update().filter(**scope).first()
    if record:
        if record.fingerprint != digest:
            raise Conflict()
        return record.result
    from .documents import pending_objects
    saved = []
    context = pending_objects.set(saved)
    try:
        result = mutation(locked)
        IdempotencyRecord.objects.create(**scope, fingerprint=digest, result=result)
    except Exception:
        for storage, object_key in saved:
            storage.delete_private_object(key=object_key)
        raise
    finally:
        pending_objects.reset(context)
    return result
