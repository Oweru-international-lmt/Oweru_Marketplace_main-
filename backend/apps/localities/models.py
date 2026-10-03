from django.core.exceptions import ValidationError
from django.db import models
from django.db.models.functions import Lower

from apps.common.models import CreatedByModel, TimeStampedModel


def _normalize_name(value):
    return (value or "").strip()


def _clean_name_field(instance):
    instance.name = _normalize_name(instance.name)
    if not instance.name:
        raise ValidationError({"name": "Name is required."})


class Region(TimeStampedModel):
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(Lower("name"), name="uniq_locality_region_name_ci"),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        _clean_name_field(self)

    def save(self, *args, **kwargs):
        self.name = _normalize_name(self.name)
        return super().save(*args, **kwargs)


class District(TimeStampedModel):
    region = models.ForeignKey(Region, on_delete=models.PROTECT, related_name="districts")
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["region__name", "name"]
        constraints = [
            models.UniqueConstraint(
                models.F("region"),
                Lower("name"),
                name="uniq_locality_district_region_name_ci",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        _clean_name_field(self)

    def save(self, *args, **kwargs):
        self.name = _normalize_name(self.name)
        return super().save(*args, **kwargs)


class Ward(TimeStampedModel):
    district = models.ForeignKey(District, on_delete=models.PROTECT, related_name="wards")
    name = models.CharField(max_length=150)

    class Meta:
        ordering = ["district__name", "name"]
        constraints = [
            models.UniqueConstraint(
                models.F("district"),
                Lower("name"),
                name="uniq_locality_ward_district_name_ci",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        _clean_name_field(self)

    def save(self, *args, **kwargs):
        self.name = _normalize_name(self.name)
        return super().save(*args, **kwargs)


class Locality(TimeStampedModel, CreatedByModel):
    class Kind(models.TextChoices):
        STREET = "street", "Street"
        VILLAGE = "village", "Village"

    ward = models.ForeignKey(Ward, on_delete=models.PROTECT, related_name="localities")
    name = models.CharField(max_length=150)
    kind = models.CharField(max_length=16, choices=Kind.choices)
    approved = models.BooleanField(default=False)

    class Meta:
        ordering = ["ward__name", "kind", "name"]
        constraints = [
            models.UniqueConstraint(
                models.F("ward"),
                models.F("kind"),
                Lower("name"),
                name="uniq_locality_ward_kind_name_ci",
            ),
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        _clean_name_field(self)

    def save(self, *args, **kwargs):
        self.name = _normalize_name(self.name)
        return super().save(*args, **kwargs)
