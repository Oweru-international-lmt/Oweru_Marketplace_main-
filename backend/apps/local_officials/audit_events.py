from types import MappingProxyType


LOCAL_OFFICIAL_PROFILE_CREATED = "local_official.profile_created"
LOCAL_OFFICIAL_PROFILE_UPDATED = "local_official.profile_updated"
LOCAL_OFFICIAL_PROFILE_DEACTIVATED = "local_official.profile_deactivated"
LOCAL_OFFICIAL_PROFILE_REACTIVATED = "local_official.profile_reactivated"
LOCAL_OFFICIAL_JURISDICTION_ASSIGNED = "local_official.jurisdiction_assigned"
LOCAL_OFFICIAL_JURISDICTION_REVOKED = "local_official.jurisdiction_revoked"

LOCAL_OFFICIAL_AUDIT_ACTIONS = MappingProxyType({
    LOCAL_OFFICIAL_PROFILE_CREATED: "Local official profile created",
    LOCAL_OFFICIAL_PROFILE_UPDATED: "Local official profile updated",
    LOCAL_OFFICIAL_PROFILE_DEACTIVATED: "Local official profile deactivated",
    LOCAL_OFFICIAL_PROFILE_REACTIVATED: "Local official profile reactivated",
    LOCAL_OFFICIAL_JURISDICTION_ASSIGNED: "Local official jurisdiction assigned",
    LOCAL_OFFICIAL_JURISDICTION_REVOKED: "Local official jurisdiction revoked",
})
