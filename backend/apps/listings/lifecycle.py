from dataclasses import dataclass
from types import MappingProxyType

from .models import Listing


TRANSITION_DRAFT_TO_ACTIVE = "DRAFT_TO_ACTIVE"
TRANSITION_ACTIVE_TO_UNDER_OFFER = "ACTIVE_TO_UNDER_OFFER"
TRANSITION_ACTIVE_TO_WITHDRAWN = "ACTIVE_TO_WITHDRAWN"
TRANSITION_ACTIVE_TO_SUSPENDED = "ACTIVE_TO_SUSPENDED"
TRANSITION_UNDER_OFFER_TO_SOLD = "UNDER_OFFER_TO_SOLD"
TRANSITION_UNDER_OFFER_TO_ACTIVE = "UNDER_OFFER_TO_ACTIVE"
TRANSITION_WITHDRAWN_TO_ACTIVE = "WITHDRAWN_TO_ACTIVE"
TRANSITION_SUSPENDED_TO_ACTIVE = "SUSPENDED_TO_ACTIVE"

LISTING_LIFECYCLE_TRANSITIONS = MappingProxyType({
    Listing.Status.DRAFT: frozenset({Listing.Status.ACTIVE}),
    Listing.Status.ACTIVE: frozenset({
        Listing.Status.UNDER_OFFER,
        Listing.Status.WITHDRAWN,
        Listing.Status.SUSPENDED,
    }),
    Listing.Status.UNDER_OFFER: frozenset({Listing.Status.SOLD, Listing.Status.ACTIVE}),
    Listing.Status.WITHDRAWN: frozenset({Listing.Status.ACTIVE}),
    Listing.Status.SUSPENDED: frozenset({Listing.Status.ACTIVE}),
    Listing.Status.SOLD: frozenset(),
})

LISTING_OPERATIONAL_TRANSITIONS = MappingProxyType({
    TRANSITION_DRAFT_TO_ACTIVE: (Listing.Status.DRAFT, Listing.Status.ACTIVE),
    TRANSITION_UNDER_OFFER_TO_ACTIVE: (Listing.Status.UNDER_OFFER, Listing.Status.ACTIVE),
    TRANSITION_WITHDRAWN_TO_ACTIVE: (Listing.Status.WITHDRAWN, Listing.Status.ACTIVE),
    TRANSITION_ACTIVE_TO_WITHDRAWN: (Listing.Status.ACTIVE, Listing.Status.WITHDRAWN),
    TRANSITION_ACTIVE_TO_SUSPENDED: (Listing.Status.ACTIVE, Listing.Status.SUSPENDED),
    TRANSITION_SUSPENDED_TO_ACTIVE: (Listing.Status.SUSPENDED, Listing.Status.ACTIVE),
})

DEFERRED_TRANSITIONS = MappingProxyType({
    TRANSITION_ACTIVE_TO_UNDER_OFFER: (Listing.Status.ACTIVE, Listing.Status.UNDER_OFFER),
    TRANSITION_UNDER_OFFER_TO_SOLD: (Listing.Status.UNDER_OFFER, Listing.Status.SOLD),
})


def is_transition_documented(source_status, target_status):
    return target_status in LISTING_LIFECYCLE_TRANSITIONS.get(source_status, frozenset())


def is_terminal_status(status):
    return not LISTING_LIFECYCLE_TRANSITIONS.get(status, frozenset())


@dataclass(frozen=True)
class ActivationRequirement:
    code: str
    status: str


@dataclass(frozen=True)
class ActivationEligibility:
    is_eligible: bool
    requirements: tuple[ActivationRequirement, ...]

    @property
    def blocked_codes(self):
        return tuple(requirement.code for requirement in self.requirements if requirement.status != "SATISFIED")


def activation_eligibility_from_requirements(requirements):
    requirement_tuple = tuple(requirements)
    return ActivationEligibility(
        is_eligible=all(requirement.status == "SATISFIED" for requirement in requirement_tuple),
        requirements=requirement_tuple,
    )
