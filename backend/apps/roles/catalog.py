from types import MappingProxyType


ROLE_BUYER = "buyer"
ROLE_OWNER = "owner"
ROLE_AGENT = "agent"
ROLE_LOCAL_OFFICIAL = "local_official"
ROLE_PROFESSIONAL = "professional"
ROLE_VERIFIER = "verifier"
ROLE_MARKETER = "marketer"
ROLE_MANAGEMENT = "management"

CANONICAL_ROLE_DEFINITIONS = MappingProxyType({
    ROLE_BUYER: "Buyer",
    ROLE_OWNER: "Owner",
    ROLE_AGENT: "Agent",
    ROLE_LOCAL_OFFICIAL: "Local official",
    ROLE_PROFESSIONAL: "Professional",
    ROLE_VERIFIER: "Verifier",
    ROLE_MARKETER: "Marketer",
    ROLE_MANAGEMENT: "Management",
})
CANONICAL_ROLE_CODES = frozenset(CANONICAL_ROLE_DEFINITIONS)

PUBLIC_ROLES = frozenset({ROLE_BUYER, ROLE_OWNER, ROLE_AGENT})
PARTNER_ROLES = frozenset({ROLE_LOCAL_OFFICIAL, ROLE_PROFESSIONAL})
STAFF_ROLES = frozenset({ROLE_VERIFIER, ROLE_MARKETER, ROLE_MANAGEMENT})
OPERATIONAL_ROLES = PARTNER_ROLES | STAFF_ROLES
ASSIGNABLE_STAFF_ROLES = frozenset({ROLE_VERIFIER, ROLE_MARKETER})

# Permission catalog compatibility remains owned by the legacy authorization app
# until M03 migrates assignment/removal services to canonical roles.
from .legacy_authorization.catalog import CATALOG, DEFAULT_ROLE_PERMISSIONS, OPTIONAL_GRANTS  # noqa: E402,F401
