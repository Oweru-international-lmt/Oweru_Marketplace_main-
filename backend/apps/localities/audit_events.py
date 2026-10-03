from types import MappingProxyType


LOCALITY_CREATED = "LOCALITY_CREATED"
LOCALITY_APPROVED = "LOCALITY_APPROVED"

LOCALITY_AUDIT_ACTIONS = MappingProxyType({
    LOCALITY_CREATED: "Locality created",
    LOCALITY_APPROVED: "Locality approved",
})
