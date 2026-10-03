from apps.audit.services import create_audit_log


ACCOUNT_REGISTERED = "ACCOUNT_REGISTERED"
LOGIN_FAILED = "LOGIN_FAILED"
ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
EMAIL_VERIFIED = "EMAIL_VERIFIED"
PASSWORD_RESET_COMPLETED = "PASSWORD_RESET_COMPLETED"
PASSWORD_CHANGED = "PASSWORD_CHANGED"
LOGOUT = "LOGOUT"
ACCOUNT_DELETION_REQUESTED = "ACCOUNT_DELETION_REQUESTED"


def record_account_event(*, action, user=None, entity_type="User", entity_id=None, before=None, after=None, request=None):
    return create_audit_log(
        actor=user,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id if entity_id is not None else (user.pk if user is not None else ""),
        before=before,
        after=after,
        request=request,
    )


def record_login_failed(*, user=None, request=None):
    return record_account_event(
        action=LOGIN_FAILED,
        user=user,
        after={"account_resolved": user is not None},
        request=request,
    )
