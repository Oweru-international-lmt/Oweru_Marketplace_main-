from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from django.db import transaction, connection
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.accounts.models import User
from apps.leads.policies import authorize, management
from apps.leads.services import audit
from .models import RateTable, RateBand


def money(value):
    if isinstance(value, (float, bool)):
        raise ValidationError("Money must be an exact whole-shilling value.")
    try:
        result = Decimal(value)
        if not result.is_finite() or result != result.to_integral_value() or result <= 0 or result > Decimal("999999999999999999"):
            raise ValueError
        return result
    except (ValueError, TypeError, InvalidOperation):
        raise ValidationError("A positive whole-shilling price is required.")


def current_rate_table():
    return RateTable.objects.filter(published_at__isnull=False, published_at__lte=timezone.now()).order_by("-published_at", "-version").first()


def lock_rate_publication():
    """Serialize publication with creation-time rate selection on PostgreSQL."""
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(5199698, 12)")


@transaction.atomic
def save_rate_draft(*, actor, values, table_id=None, request=None):
    actor = authorize(actor, "commission.manage")
    if not management(actor):
        raise PermissionDenied("Management required.")
    values = dict(values)
    bands = values.pop("bands")
    if table_id:
        table = RateTable.objects.select_for_update().get(pk=table_id)
        if table.published_at:
            raise ValidationError("Published versions cannot be edited.")
        if values["version"] != table.version:
            raise ValidationError("Draft version identifiers cannot be changed.")
        table.total_rate = values["total_rate"]
        table.full_clean()
        table.save()
        table.bands.all().delete()
    else:
        if RateTable.objects.filter(version=values["version"]).exists():
            raise ValidationError("Rate version already exists.")
        table = RateTable.objects.create(**values)
    from django.core.exceptions import ValidationError as ModelValidationError
    try:
        for band in bands:
            row = RateBand(table=table, **band)
            row.full_clean()
            row.save()
    except ModelValidationError as exc:
        raise ValidationError(exc.message_dict) from exc
    audit(actor, "rate_table.draft_saved", table, after={"version": table.version}, request=request)
    return table


@transaction.atomic
def publish_rate_table(*, actor, table_id, request=None):
    actor = authorize(actor, "commission.manage")
    if not management(actor):
        raise PermissionDenied("Management is required.")
    lock_rate_publication()
    # Serialize publishers independently of which draft they publish.
    User.objects.select_for_update().get(pk=actor.pk)
    table = RateTable.objects.select_for_update().get(pk=table_id)
    if table.published_at:
        return table
    bands = list(table.bands.select_for_update().order_by("lower"))
    if not bands or bands[0].lower != 0 or bands[-1].upper is not None:
        raise ValidationError("Bands must cover all whole-shilling prices from zero through an unbounded final band.")
    next_lower = Decimal(0)
    for band in bands:
        if band.lower != next_lower or band.oweru_rate + band.agent_rate != table.total_rate:
            raise ValidationError("Rate bands must have no gaps/overlaps and rates must sum to the total.")
        if band.upper is None and band != bands[-1]:
            raise ValidationError("Only the last band may be unbounded.")
        if band.upper is not None and band.upper < band.lower:
            raise ValidationError("Invalid rate bounds.")
        next_lower = band.upper + 1 if band.upper is not None else None
    table.published_at = timezone.now()
    table.published_by = actor
    table.full_clean()
    table.save()
    audit(actor, "rate_table.published", table, after={"version": table.version}, request=request)
    return table


class CommissionService:
    @staticmethod
    def calculate(*, owner_price, selling_price, rate_table, lister_kind):
        selling_price = money(selling_price)
        owner_price = money(owner_price) if lister_kind == "AGENT" else selling_price
        if lister_kind not in {"AGENT", "OWNER"} or selling_price < owner_price or not rate_table.published_at:
            raise ValidationError("Invalid listing prices or unpublished rate version.")
        bands = list(rate_table.bands.filter(lower__lte=selling_price).filter(Q(upper__isnull=True) | Q(upper__gte=selling_price)))
        if len(bands) != 1:
            raise ValidationError("Exactly one applicable band is required.")
        band = bands[0]
        total, x = rate_table.total_rate, band.oweru_rate
        if x + band.agent_rate != total:
            raise ValidationError("Band rates do not reconcile.")
        rounded = lambda value: value.quantize(Decimal(1), rounding=ROUND_HALF_UP)
        owner = rounded(owner_price * (1 - (total if lister_kind == "AGENT" else x)))
        payout = rounded(owner_price * (total - x) + selling_price - owner_price) if lister_kind == "AGENT" else Decimal(0)
        collects = selling_price - owner
        retained = collects - payout
        if retained < 0:
            raise ValidationError("Rounding would produce a negative retained amount.")
        return {"owner_price": owner_price, "final_selling_price": selling_price, "rate_band": band, "total_rate": total, "oweru_rate": x, "buyer_to_owner": owner, "buyer_to_oweru": collects, "oweru_keeps": retained, "agent_payout": payout}
