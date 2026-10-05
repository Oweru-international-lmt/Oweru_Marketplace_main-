from django.conf import settings
from django.contrib.gis.db import models as gis_models
from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import TimeStampedModel
from apps.localities.models import District, Locality, Region, Ward


class PermanentPropertyRecordQuerySet(models.QuerySet):
    def delete(self):
        raise RuntimeError("Property records cannot be deleted.")


class PropertyRecord(TimeStampedModel):
    class Category(models.TextChoices):
        LAND = "LAND", "Land"
        HOUSE = "HOUSE", "House"
        COMMERCIAL = "COMMERCIAL", "Commercial"

    class TitleType(models.TextChoices):
        REGISTERED_TITLE = "REGISTERED_TITLE", "Registered title"
        RESIDENTIAL_LICENCE = "RESIDENTIAL_LICENCE", "Residential licence"
        SALE_AGREEMENT = "SALE_AGREEMENT", "Sale agreement"
        CCRO = "CCRO", "CCRO"
        VILLAGE_RECORDS = "VILLAGE_RECORDS", "Village records"
        NONE = "NONE", "None"
        UNKNOWN = "UNKNOWN", "Unknown"

    property_id = models.CharField(max_length=50, unique=True)
    category = models.CharField(max_length=20, choices=Category.choices)
    pin = gis_models.PointField(srid=4326)
    boundary = gis_models.PolygonField(srid=4326, null=True, blank=True)
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="property_records")
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="property_records")
    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="property_records")
    locality = models.ForeignKey(Locality, on_delete=models.PROTECT, related_name="property_records")
    stated_size = models.DecimalField(max_digits=18, decimal_places=2)
    size_unit = models.CharField(max_length=20)
    title_type = models.CharField(max_length=32, choices=TitleType.choices)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        editable=False,
        related_name="property_records_created",
    )

    objects = PermanentPropertyRecordQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(stated_size__gt=0), name="property_stated_size_positive"),
        ]

    def __str__(self):
        return self.property_id

    def delete(self, *args, **kwargs):
        raise RuntimeError("Property records cannot be deleted.")

    def clean(self):
        super().clean()
        errors = {}

        if self.locality_id and self.ward_id and self.locality.ward_id != self.ward_id:
            errors["locality"] = "Locality must belong to the selected ward."
        if self.ward_id and self.district_id and self.ward.district_id != self.district_id:
            errors["ward"] = "Ward must belong to the selected district."
        if self.district_id and self.region_id and self.district.region_id != self.region_id:
            errors["district"] = "District must belong to the selected region."
        if self.stated_size is not None and self.stated_size <= 0:
            errors["stated_size"] = "Stated size must be greater than zero."

        if errors:
            raise ValidationError(errors)


class PermanentPossibleDuplicateQuerySet(models.QuerySet):
    def delete(self):
        raise RuntimeError("Possible duplicate records cannot be deleted.")


class PossibleDuplicate(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        CONFIRMED_DUPLICATE = "CONFIRMED_DUPLICATE", "Confirmed duplicate"
        NOT_DUPLICATE = "NOT_DUPLICATE", "Not duplicate"

    SIGNAL_PIN_PROXIMITY = "PIN_PROXIMITY"
    SIGNAL_SIZE_SIMILARITY = "SIZE_SIMILARITY"
    SIGNAL_PHOTO_SIMILARITY = "PHOTO_SIMILARITY"
    SIGNAL_CHOICES = (
        (SIGNAL_PIN_PROXIMITY, "Pin proximity"),
        (SIGNAL_SIZE_SIMILARITY, "Size similarity"),
        (SIGNAL_PHOTO_SIMILARITY, "Photo similarity"),
    )
    ALLOWED_SIGNALS = frozenset(code for code, _ in SIGNAL_CHOICES)

    property_a = models.ForeignKey(PropertyRecord, on_delete=models.PROTECT, related_name="possible_duplicates_as_a")
    property_b = models.ForeignKey(PropertyRecord, on_delete=models.PROTECT, related_name="possible_duplicates_as_b")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING, db_index=True)
    signals = models.JSONField(default=list)
    distance_meters = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    size_difference_percent = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="reviewed_possible_duplicates",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=1000, blank=True)

    objects = PermanentPossibleDuplicateQuerySet.as_manager()

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["property_a", "property_b"], name="possible_duplicate_unique_pair"),
            models.CheckConstraint(
                condition=~models.Q(property_a=models.F("property_b")),
                name="possible_duplicate_no_self_pair",
            ),
            models.CheckConstraint(
                condition=models.Q(distance_meters__isnull=True) | models.Q(distance_meters__gte=0),
                name="possible_duplicate_distance_non_negative",
            ),
            models.CheckConstraint(
                condition=models.Q(size_difference_percent__isnull=True) | models.Q(size_difference_percent__gte=0),
                name="possible_duplicate_size_diff_non_negative",
            ),
        ]

    def __str__(self):
        return f"{self.property_a.property_id}<->{self.property_b.property_id}:{self.status}"

    def _canonicalize_pair(self):
        if self.property_a_id and self.property_b_id and str(self.property_a_id) > str(self.property_b_id):
            self.property_a, self.property_b = self.property_b, self.property_a

    def clean(self):
        super().clean()
        errors = {}
        self._canonicalize_pair()

        if self.property_a_id and self.property_b_id and self.property_a_id == self.property_b_id:
            errors["property_b"] = "A property cannot be a possible duplicate of itself."

        if not isinstance(self.signals, list) or not self.signals:
            errors["signals"] = "At least one duplicate signal is required."
        else:
            normalized = []
            for signal in self.signals:
                if signal not in self.ALLOWED_SIGNALS:
                    errors["signals"] = "Signals must use known duplicate signal codes."
                    break
                if signal not in normalized:
                    normalized.append(signal)
            self.signals = sorted(normalized)

        if self.distance_meters is not None and self.distance_meters < 0:
            errors["distance_meters"] = "Distance must be non-negative."
        if self.size_difference_percent is not None and self.size_difference_percent < 0:
            errors["size_difference_percent"] = "Size difference must be non-negative."

        if self.review_note:
            self.review_note = " ".join(self.review_note.split())

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if not self._state.adding:
            return super().save(*args, **kwargs)
        self._canonicalize_pair()
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError("Possible duplicate records cannot be deleted.")
