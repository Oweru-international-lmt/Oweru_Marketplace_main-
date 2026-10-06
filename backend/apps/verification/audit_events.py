from types import MappingProxyType


VERIFICATION_DOCUMENT_SUBMITTED = "verification.document_submitted"
VERIFICATION_DOCUMENT_APPROVED = "verification.document_approved"
VERIFICATION_DOCUMENT_REJECTED = "verification.document_rejected"
VERIFICATION_DOCUMENT_REVOKED = "verification.document_revoked"
VERIFICATION_DOCUMENT_EXPIRED = "verification.document_expired"
VERIFICATION_FIELD_SUBMITTED = "verification.field_submitted"
VERIFICATION_FIELD_APPROVED = "verification.field_approved"
VERIFICATION_FIELD_REJECTED = "verification.field_rejected"
VERIFICATION_FIELD_REVOKED = "verification.field_revoked"
VERIFICATION_FIELD_EXPIRED = "verification.field_expired"
VERIFICATION_PROPERTY_CHANGE_INVALIDATED = "verification.property_change_invalidated"

VERIFICATION_AUDIT_ACTIONS = MappingProxyType({
    VERIFICATION_DOCUMENT_SUBMITTED: "Document verification submitted",
    VERIFICATION_DOCUMENT_APPROVED: "Document verification approved",
    VERIFICATION_DOCUMENT_REJECTED: "Document verification rejected",
    VERIFICATION_DOCUMENT_REVOKED: "Document verification revoked",
    VERIFICATION_DOCUMENT_EXPIRED: "Document verification expired",
    VERIFICATION_FIELD_SUBMITTED: "Field verification submitted",
    VERIFICATION_FIELD_APPROVED: "Field verification approved",
    VERIFICATION_FIELD_REJECTED: "Field verification rejected",
    VERIFICATION_FIELD_REVOKED: "Field verification revoked",
    VERIFICATION_FIELD_EXPIRED: "Field verification expired",
    VERIFICATION_PROPERTY_CHANGE_INVALIDATED: "Property verification invalidated by property change",
})
