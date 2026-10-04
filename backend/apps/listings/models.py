from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimeStampedModel
from apps.properties.models import PropertyRecord


class PermanentListingQuerySet(models.QuerySet):
    def delete(self):
        raise RuntimeError("Listings cannot be deleted.")


class Listing(TimeStampedModel):
    class ListerKind(models.TextChoices):
        OWNER = "OWNER", "Owner"
        AGENT = "AGENT", "Agent"

    class Currency(models.TextChoices):
        TZS = "TZS", "Tanzanian shilling"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Draft"
        ACTIVE = "ACTIVE", "Active"
        UNDER_OFFER = "UNDER_OFFER", "Under offer"
        SOLD = "SOLD", "Sold"
        WITHDRAWN = "WITHDRAWN", "Withdrawn"
        SUSPENDED = "SUSPENDED", "Suspended"

    listing_id = models.CharField(max_length=50, unique=True)
    property = models.ForeignKey(PropertyRecord, on_delete=models.PROTECT, related_name="listings")
    lister = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="listings",
    )
    lister_kind = models.CharField(max_length=16, choices=ListerKind.choices)
    selling_price = models.DecimalField(max_digits=18, decimal_places=0)
    owner_price = models.DecimalField(max_digits=18, decimal_places=0)
    currency = models.CharField(max_length=3, choices=Currency.choices, default=Currency.TZS)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.DRAFT, db_index=True)
    description = models.TextField(blank=True)
    features = models.JSONField(default=list, blank=True)

    objects = PermanentListingQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(selling_price__gt=0), name="listing_selling_price_positive"),
            models.CheckConstraint(condition=models.Q(owner_price__gt=0), name="listing_owner_price_positive"),
            models.CheckConstraint(condition=models.Q(lister_kind__in=["OWNER", "AGENT"]), name="listing_lister_kind_valid"),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["DRAFT", "ACTIVE", "UNDER_OFFER", "SOLD", "WITHDRAWN", "SUSPENDED"],
                ),
                name="listing_status_valid",
            ),
            models.CheckConstraint(condition=models.Q(currency__in=["TZS"]), name="listing_currency_valid"),
            models.CheckConstraint(
                condition=(
                    models.Q(lister_kind="OWNER", owner_price=models.F("selling_price"))
                    | models.Q(lister_kind="AGENT", selling_price__gte=models.F("owner_price"))
                ),
                name="listing_price_matches_lister_kind",
            ),
        ]

    def __str__(self):
        return self.listing_id

    def delete(self, *args, **kwargs):
        raise RuntimeError("Listings cannot be deleted.")

    def clean(self):
        super().clean()
        errors = {}

        if self.selling_price is not None and self.selling_price <= 0:
            errors["selling_price"] = "Selling price must be greater than zero."
        if self.owner_price is not None and self.owner_price <= 0:
            errors["owner_price"] = "Owner price must be greater than zero."
        if self.lister_kind == self.ListerKind.OWNER and self.owner_price != self.selling_price:
            errors["owner_price"] = "Owner listings must use the selling price as the owner price."
        if self.lister_kind == self.ListerKind.AGENT and self.selling_price is not None and self.owner_price is not None:
            if self.selling_price < self.owner_price:
                errors["selling_price"] = "Selling price must be greater than or equal to owner price."

        if errors:
            raise ValidationError(errors)
