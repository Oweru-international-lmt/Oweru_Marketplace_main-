LISTING_CREATED = "listing.created"
LISTING_UPDATED = "listing.updated"
LISTING_ACTIVATED = "listing.activated"
LISTING_WITHDRAWN = "listing.withdrawn"
LISTING_SUSPENDED = "listing.suspended"
LISTING_RESTORED = "listing.restored"

LISTING_AUDIT_ACTIONS = frozenset({
    LISTING_CREATED,
    LISTING_UPDATED,
    LISTING_ACTIVATED,
    LISTING_WITHDRAWN,
    LISTING_SUSPENDED,
    LISTING_RESTORED,
})
