from .legacy_event_stream.services import record_event as legacy_record_event
from .models import AuditLog


def create_audit_log(*, action, entity_type, entity_id="", actor=None, before=None, after=None, request=None):
    ip_address = None
    user_agent = ""
    if request is not None:
        ip_address = request.META.get("REMOTE_ADDR") or None
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:2000]
        request_user = getattr(request, "user", None)
        if actor is None and getattr(request_user, "is_authenticated", False):
            actor = request_user

    return AuditLog.objects.create(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before=before or {},
        after=after or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def record_sensitive_access(*, actor, entity_type, entity_id, request=None):
    return create_audit_log(
        actor=actor,
        action="sensitive_data.accessed",
        entity_type=entity_type,
        entity_id=entity_id,
        request=request,
    )
