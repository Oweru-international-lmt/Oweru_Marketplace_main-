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
