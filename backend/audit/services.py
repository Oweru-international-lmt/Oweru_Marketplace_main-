from .models import AuditEvent


def record_event(*, action, entity_type, entity_id="", actor=None, before_state=None, after_state=None, request=None):
    ip_address = None
    user_agent = ""
    if request is not None:
        # Do not trust proxy headers by default; REMOTE_ADDR is the connecting peer.
        ip_address = request.META.get("REMOTE_ADDR") or None
        user_agent = request.META.get("HTTP_USER_AGENT", "")[:2000]
        if actor is None and getattr(request, "user", None) and request.user.is_authenticated:
            actor = request.user
    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        before_state=before_state or {},
        after_state=after_state or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
