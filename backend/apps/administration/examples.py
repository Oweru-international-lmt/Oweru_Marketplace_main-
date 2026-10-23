"""Decision D5: starting values the responsible people review and change.

The commission table is edited by Management (PAY-01) and the full check fee
by the Director (FUL-01). These are examples, not rules: the seed command
creates them only where nothing exists yet, and the settings screen shows
them as reference.
"""
from decimal import Decimal

TOTAL_RATE = Decimal("0.10")

# (lower TSh, upper TSh or None, Oweru share, agent share)
RATE_BANDS = (
    (Decimal("0"), Decimal("50000000"), Decimal("0.04"), Decimal("0.06")),
    (Decimal("50000001"), Decimal("200000000"), Decimal("0.03"), Decimal("0.07")),
    (Decimal("200000001"), Decimal("500000000"), Decimal("0.025"), Decimal("0.075")),
    (Decimal("500000001"), None, Decimal("0.02"), Decimal("0.08")),
)

FULL_CHECK_FEE = 450000

# What the example fee is built from; keys match the frontend text.
FULL_CHECK_FEE_PARTS = (
    ("registry", 40000),
    ("local_office", 30000),
    ("boundary", 130000),
    ("planning", 100000),
    ("review", 150000),
)


def as_payload():
    return {
        "rate_table": {
            "total_rate": str(TOTAL_RATE),
            "bands": [{"lower": str(lower), "upper": str(upper) if upper is not None else None, "oweru_rate": str(oweru), "agent_rate": str(agent)} for lower, upper, oweru, agent in RATE_BANDS],
        },
        "full_check_fee": FULL_CHECK_FEE,
        "full_check_fee_parts": [{"key": key, "amount": amount} for key, amount in FULL_CHECK_FEE_PARTS],
    }
