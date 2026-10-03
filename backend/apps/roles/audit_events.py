from types import MappingProxyType


ROLE_ASSIGNED = "ROLE_ASSIGNED"
ROLE_REMOVED = "ROLE_REMOVED"
USER_SUSPENDED = "USER_SUSPENDED"
USER_RESTORED = "USER_RESTORED"
SETTINGS_CHANGED = "SETTINGS_CHANGED"
SENSITIVE_DATA_ACCESSED = "SENSITIVE_DATA_ACCESSED"

RBAC_AUDIT_ACTIONS = MappingProxyType({
    ROLE_ASSIGNED: "Canonical role assigned",
    ROLE_REMOVED: "Canonical role removed",
    USER_SUSPENDED: "User suspended",
    USER_RESTORED: "User restored",
    SETTINGS_CHANGED: "Settings changed",
    SENSITIVE_DATA_ACCESSED: "Sensitive data accessed",
})
