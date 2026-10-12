import re
from collections import defaultdict, Counter
from datetime import timedelta
from decimal import Decimal
from statistics import median
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from apps.audit.models import AuditLog
from apps.audit.services import create_audit_log
from apps.leads.policies import authorize
from apps.listings.public_analytics import SEARCH_FILTER_FIELDS
from .models import MarketEvent, MarketAggregate, AggregateRun, LeadAttribution, DealPriceSnapshot


def staff(actor, permission="analytics.view"):
    actor = authorize(actor, permission)
    if actor.account_category != "operational" or not any(actor.has_role(role) for role in ["marketer", "management"]):
        raise PermissionDenied("Market monitoring staff are required.")
    return actor


def source_tag(value):
    if not value:
        return ""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValidationError("Invalid marketing source tag.")
    return value


def dimensions(prop):
    return {"region": prop.region_id, "district": prop.district_id, "ward": prop.ward_id, "category": prop.category}


def price_range(minimum=None, maximum=None):
    def bucket(value):
        if value is None:
            return "ANY"
        price = Decimal(str(value))
        if price < 10000000:
            return "UNDER_10M"
        if price < 100000000:
            return "10M_TO_100M"
        return "100M_PLUS"
    return bucket(minimum) + ":" + bucket(maximum)


def record_search(params):
    from apps.listings.public_search import validate_public_listing_search_params
    values = validate_public_listing_search_params(params)
    MarketEvent.objects.create(kind="SEARCH", region=values.get("region"), district=values.get("district"), ward=values.get("ward"), category=values.get("category", ""), price_range=price_range(values.get("min_price"), values.get("max_price")), filters=sorted(set(values) & SEARCH_FILTER_FIELDS), source_tag=source_tag(values.get("source_tag", "")))


def record_view(listing, source=""):
    MarketEvent.objects.create(kind="VIEW", **dimensions(listing.property), price_range=price_range(listing.selling_price, listing.selling_price), source_tag=source_tag(source))


def record_enquiry(lead, source=""):
    source = source_tag(source)
    LeadAttribution.objects.create(lead=lead, source_tag=source)
    MarketEvent.objects.create(kind="ENQUIRY", **dimensions(lead.property), price_range=price_range(lead.listing.selling_price, lead.listing.selling_price), source_tag=source)


def key(dim):
    return ":".join(str(dim.get(name) or "") for name in ["region", "district", "ward", "category"])


def statistics(values):
    return {"count": len(values), "average": float(sum(values) / len(values)) if values else None, "median": float(median(values)) if values else None}


def sqm(size, unit):
    factors = {"sqm": Decimal(1), "m2": Decimal(1), "acre": Decimal("4046.8564224"), "acres": Decimal("4046.8564224"), "hectare": Decimal(10000), "hectares": Decimal(10000), "ha": Decimal(10000)}
    factor = factors.get(unit.lower())
    return size * factor if factor and size > 0 else None


@transaction.atomic
def refresh():
    """One consistent nightly snapshot; request paths read only materialized cells."""
    from apps.free_checks.services import lock_phone
    from apps.listings.models import Listing
    from apps.leads.models import Lead
    from apps.deals.models import Deal
    from apps.free_checks.models import FreeCheck
    from apps.local_officials.models import OfficialLocalityCoverage
    from apps.professionals.models import ProfessionalProfile
    from apps.verification.services import annotate_listing_queryset_with_effective_verification_level
    lock_phone("analytics:refresh")
    now, today = timezone.now(), timezone.localdate()
    cells = {}

    def cell(day, kind, dim):
        identifier = (day, kind, key(dim))
        if identifier not in cells:
            cells[identifier] = {"day": day, "kind": kind, "area_key": identifier[2], **dim, "metrics": {}}
        return cells[identifier]["metrics"]

    def inc(metrics, name, value=1):
        metrics[name] = metrics.get(name, 0) + value

    def counter(metrics, name, code):
        values = metrics.setdefault(name, {})
        values[code] = values.get(code, 0) + 1

    stock = Listing.objects.filter(status__in=["ACTIVE", "UNDER_OFFER"]).select_related("property")
    stock = annotate_listing_queryset_with_effective_verification_level(stock, at=now)
    for listing in stock.iterator(chunk_size=500):
        metrics = cell(today, "STOCK", dimensions(listing.property))
        inc(metrics, "active_listings")
        metrics.setdefault("prices", []).append(float(listing.selling_price))
        area = sqm(listing.property.stated_size, listing.property.size_unit)
        if area:
            metrics.setdefault("sqm_prices", []).append(float(listing.selling_price / area))
        counter(metrics, "verification_mix", str(listing.effective_verification_level))
        metrics.setdefault("listers", set()).add(listing.lister_id)
    first_listing_listers = set()
    for listing in Listing.objects.filter(created_at__lte=now).select_related("property").order_by("created_at", "pk").iterator(chunk_size=500):
        metrics = cell(timezone.localdate(listing.created_at), "ACTIVITY", dimensions(listing.property))
        inc(metrics, "listings_created")
        if listing.lister_id not in first_listing_listers:
            first_listing_listers.add(listing.lister_id)
            inc(metrics, "new_listers")

    for row in MarketEvent.objects.filter(created_at__lte=now).iterator(chunk_size=1000):
        dim = {name: getattr(row, name) for name in ["region", "district", "ward", "category"]}
        metrics = cell(timezone.localdate(row.created_at), "ACTIVITY", dim)
        inc(metrics, {"SEARCH": "searches", "VIEW": "views", "ENQUIRY": "enquiry_events"}[row.kind])
        for field in row.filters:
            counter(metrics, "filter_uses", field)
        counter(metrics, "demand_price_ranges", row.price_range)
        if row.source_tag:
            counter(metrics, "sources_" + row.kind.lower(), row.source_tag)

    activations = {}
    for entry in AuditLog.objects.filter(action="listing.activated", created_at__lte=now).order_by("created_at").values("entity_id", "created_at").iterator():
        activations.setdefault(entry["entity_id"], entry["created_at"])
    first_leads = set()
    for lead in Lead.objects.filter(created_at__lte=now).select_related("property").prefetch_related("transitions").order_by("created_at").iterator(chunk_size=500):
        metrics = cell(timezone.localdate(lead.created_at), "ACTIVITY", dimensions(lead.property))
        inc(metrics, "enquiries")
        transitions = list(lead.transitions.all())
        stages = {"NEW", *(entry.to_stage for entry in transitions)}
        for stage in stages:
            counter(metrics, "cohort_stages", stage)
        response = [entry.created_at for entry in transitions if entry.to_stage == "CONTACTED"]
        if response:
            inc(metrics, "response_seconds_sum", max(0, (min(response) - lead.created_at).total_seconds()))
            inc(metrics, "response_count")
        if lead.listing_id not in first_leads:
            first_leads.add(lead.listing_id)
            activated = activations.get(str(lead.listing_id))
            if activated and lead.created_at >= activated:
                inc(metrics, "first_enquiry_days_sum", (lead.created_at - activated).total_seconds() / 86400)
                inc(metrics, "first_enquiry_count")
            else:
                inc(metrics, "first_enquiry_activation_missing")

    from apps.marketing.models import CampaignDelivery
    for delivery in CampaignDelivery.objects.select_related("campaign").iterator(chunk_size=500):
        metrics = cell(timezone.localdate(delivery.created_at), "ACTIVITY", {"region": None, "district": None, "ward": None, "category": ""})
        campaigns = metrics.setdefault("campaigns", {})
        results = campaigns.setdefault(delivery.campaign.source_tag, {"recipients": 0, "sent": 0, "failed": 0, "cancelled": 0, "clicks": 0})
        results["recipients"] += 1
        if delivery.status in {"SENT", "FAILED", "CANCELLED"}:
            results[delivery.status.lower()] += 1
        if delivery.clicked_at:
            results["clicks"] += 1
    # Completed deals have a frozen final price. New closing snapshots provide
    # the listed-price comparison; historical discounts remain explicitly missing.
    for deal in Deal.objects.filter(state="COMPLETE", completed_at__lte=now).select_related("property", "dealpricesnapshot", "lead__leadattribution").iterator(chunk_size=500):
        metrics = cell(timezone.localdate(deal.completed_at), "ACTIVITY", dimensions(deal.property))
        inc(metrics, "won_deals")
        inc(metrics, "won_value", float(deal.final_selling_price))
        snapshot = getattr(deal, "dealpricesnapshot", None)
        if snapshot:
            inc(metrics, "discount_sum", float(snapshot.listed_price - deal.final_selling_price))
            inc(metrics, "discount_count")
        else:
            inc(metrics, "discount_history_missing")
        activated = activations.get(str(deal.listing_id))
        if activated and deal.completed_at >= activated:
            inc(metrics, "sale_days_sum", (deal.completed_at - activated).total_seconds() / 86400)
            inc(metrics, "sale_count")
        else:
            inc(metrics, "sale_activation_missing")
        attribution = getattr(deal.lead, "leadattribution", None)
        if attribution and attribution.source_tag:
            counter(metrics, "sources_won", attribution.source_tag)

    for check in FreeCheck.objects.filter(created_at__lte=now).select_related("property").iterator(chunk_size=500):
        metrics = cell(timezone.localdate(check.created_at), "ACTIVITY", dimensions(check.property))
        inc(metrics, "free_checks")
        for name, verdict in check.verdicts.items():
            counter(metrics, "free_check_results", name + ":" + verdict)
        if "MISMATCH" in check.verdicts.values():
            inc(metrics, "free_check_mismatches")

    coverage = OfficialLocalityCoverage.objects.filter(official__is_active=True, official__user__is_active=True, revoked_at__isnull=True, starts_at__lte=now, locality__approved=True).filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now)).select_related("locality__ward__district", "official__user")
    for row in coverage:
        if not row.official.user.has_role("local_official") or not row.official.user.has_marketplace_permission("verification.complete_task"):
            continue
        district = row.locality.ward.district
        metrics = cell(today, "COVERAGE", {"region": district.region_id, "district": district.pk, "ward": row.locality.ward_id, "category": ""})
        metrics.setdefault("covered_localities", set()).add(row.locality_id)
    from apps.localities.models import District
    districts = list(District.objects.all())
    for profile in ProfessionalProfile.objects.filter(status="ACTIVE", user__is_active=True).select_related("user").prefetch_related("regions", "districts"):
        if not profile.user.has_role("professional") or not profile.user.has_marketplace_permission("verification.complete_task"):
            continue
        regions = {row.pk for row in profile.regions.all()}
        covered = {row.pk for row in profile.districts.all()}
        for district in districts:
            if district.region_id in regions or district.pk in covered:
                metrics = cell(today, "COVERAGE", {"region": district.region_id, "district": district.pk, "ward": None, "category": ""})
                counter(metrics, "professional_types", profile.professional_type)

    for values in cells.values():
        metrics = values["metrics"]
        if values["kind"] == "STOCK":
            metrics["_selling_samples"] = metrics["prices"][:]
            metrics["_sqm_samples"] = metrics.get("sqm_prices", [])[:]
            metrics["selling_price"] = statistics(metrics.pop("prices"))
            metrics["price_per_sqm"] = statistics(metrics.pop("sqm_prices", []))
            metrics["active_listers"] = len(metrics.pop("listers"))
            metrics["listings_per_lister"] = metrics["active_listings"] / metrics["active_listers"]
        if "covered_localities" in metrics:
            metrics["covered_localities"] = len(metrics["covered_localities"])
    # Activity is rebuilt from append-only facts. Stock/coverage history starts
    # with the first actual refresh; earlier states are never fabricated.
    MarketAggregate.objects.filter(kind="ACTIVITY").delete()
    MarketAggregate.objects.filter(day=today, kind__in=["STOCK", "COVERAGE"]).delete()
    MarketAggregate.objects.bulk_create([MarketAggregate(**values) for values in cells.values()], batch_size=500)
    monthly = {}
    for daily in MarketAggregate.objects.filter(kind="STOCK").order_by("day").iterator(chunk_size=500):
        month = daily.day.replace(day=1)
        identifier = (month, daily.area_key)
        if identifier not in monthly:
            monthly[identifier] = {"day": month, "kind": "MONTHLY", "area_key": daily.area_key, "region": daily.region, "district": daily.district, "ward": daily.ward, "category": daily.category, "metrics": {"observed_days": 0, "prices": [], "sqm_prices": [], "active_listing_days": 0}}
        metrics = monthly[identifier]["metrics"]
        metrics["observed_days"] += 1
        metrics["prices"].extend(daily.metrics.get("_selling_samples", []))
        metrics["sqm_prices"].extend(daily.metrics.get("_sqm_samples", []))
        metrics["active_listing_days"] += daily.metrics["active_listings"]
        metrics["latest_active_listings"] = daily.metrics["active_listings"]
        metrics["last_observed_day"] = daily.day.isoformat()
    for values in monthly.values():
        metrics = values["metrics"]
        metrics["selling_price"] = statistics(metrics.pop("prices"))
        metrics["price_per_sqm"] = statistics(metrics.pop("sqm_prices"))
        metrics["average_active_listings"] = metrics["active_listing_days"] / metrics["observed_days"]
    MarketAggregate.objects.filter(kind="MONTHLY").delete()
    MarketAggregate.objects.bulk_create([MarketAggregate(**values) for values in monthly.values()], batch_size=500)
    run = AggregateRun.objects.create(completed_at=now, cells=len(cells) + len(monthly))
    return run.cells


def panel(*, actor, filters, export=False, request=None):
    actor = staff(actor, "analytics.export" if export else "analytics.view")
    rows = MarketAggregate.objects.filter(day__gte=filters["start"], day__lte=filters["end"])
    # Monthly price views use complete observed calendar months. Activity and
    # daily snapshots retain the exact requested date boundaries.
    if filters.get("kind") == "MONTHLY":
        rows = MarketAggregate.objects.filter(day__gte=filters["start"].replace(day=1), day__lte=filters["end"].replace(day=1))
    for name in ["region", "district", "category"]:
        if filters.get(name):
            if name == "category":
                rows = rows.filter(Q(category=filters[name]) | Q(kind="COVERAGE"))
            else:
                rows = rows.filter(**{name: filters[name]})
    if filters.get("kind"):
        rows = rows.filter(kind=filters["kind"])
    rows = rows.order_by("day", "kind", "area_key")
    count = rows.count()
    if count > 10000:
        raise ValidationError("Narrow the view to at most 10,000 aggregate cells.")
    result = list(rows.values("day", "kind", "region", "district", "ward", "category", "metrics"))
    for row in result:
        metrics = row["metrics"]
        for internal in ["_selling_samples", "_sqm_samples"]:
            metrics.pop(internal, None)
        if row["kind"] == "STOCK":
            metrics["verification_share"] = {level: count / metrics["active_listings"] for level, count in metrics.get("verification_mix", {}).items()}
        for name, numerator, denominator in [("average_response_seconds", "response_seconds_sum", "response_count"), ("average_time_to_first_enquiry_days", "first_enquiry_days_sum", "first_enquiry_count"), ("average_time_to_sale_days", "sale_days_sum", "sale_count"), ("average_discount", "discount_sum", "discount_count")]:
            if row["kind"] == "ACTIVITY":
                metrics[name] = metrics.get(numerator, 0) / metrics[denominator] if metrics.get(denominator) else None
        if row["kind"] == "ACTIVITY":
            reached = metrics.get("cohort_stages", {})
            metrics["conversion"] = {f"{start}_to_{end}": reached.get(end, 0) / reached[start] if reached.get(start) else None for start, end in [("NEW", "VIEWING"), ("VIEWING", "CLOSING"), ("CLOSING", "WON")]}
            metrics["heat"] = {"searches": metrics.get("searches", 0), "enquiries": metrics.get("enquiries", 0), "won_deals": metrics.get("won_deals", 0)}
    latest = AggregateRun.objects.order_by("-completed_at").first()
    create_audit_log(actor=actor, action="analytics.exported" if export else "analytics.viewed", entity_type="MarketAggregate", after={"cells": count}, request=request)
    return {"generated_at": latest.completed_at if latest else None, "stale": latest is None or timezone.now() - latest.completed_at > timedelta(hours=26), "rows": result, "limitations": ["Stock and coverage history begin at the first successful refresh; rows are daily snapshots.", "MONTHLY prices weight each observed daily active-listing snapshot; months include only observed days and use full calendar-month boundaries.", "Conversion uses enquiry-date cohorts with outcomes known at refresh time.", "Unattributed searches and outside Free Checks retain unknown area/category rather than inferred locations.", "Heat values are by administrative area; no personal details or exact property coordinates are returned.", "Activation timing and historic discounts are null where authoritative audit/snapshot data is missing.", "Marketing source tags are caller-supplied attribution, not proof of a visitor's identity."]}
