from django.conf import settings
from django.db import models
from django.db.models import Q
from apps.common.models import TimeStampedModel


class ProfessionalProfile(TimeStampedModel):
    class Type(models.TextChoices):
        AFISA_MIPANGO_MIJI = "AFISA_MIPANGO_MIJI", "Afisa Mipango Miji"
        PLANNER = "PLANNER", "Planner"
        SURVEYOR = "SURVEYOR", "Surveyor"

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="professional_profile")
    professional_type = models.CharField(max_length=24, choices=Type.choices)
    registration_number = models.CharField(max_length=100, unique=True)
    national_id_number = models.CharField(max_length=100)
    status = models.CharField(max_length=16, choices=[("ACTIVE", "Active"), ("INACTIVE", "Inactive")], default="ACTIVE")
    verified_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="professionals_verified")
    verified_at = models.DateTimeField()
    regions = models.ManyToManyField("localities.Region", related_name="professional_profiles")
    districts = models.ManyToManyField("localities.District", related_name="professional_profiles")

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(professional_type__in=["AFISA_MIPANGO_MIJI", "PLANNER", "SURVEYOR"]), name="professional_type_valid"),
            models.CheckConstraint(condition=Q(status__in=["ACTIVE", "INACTIVE"]), name="professional_status_valid"),
            models.CheckConstraint(condition=~Q(registration_number="") & ~Q(national_id_number=""), name="professional_registration_required"),
        ]
        indexes = [models.Index(fields=["professional_type", "status"], name="professional_active_type_idx")]
