from django.db import models
from rest_framework.exceptions import ValidationError


class ImmutableQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Submitted records are immutable; append a correction version.")

    def delete(self):
        raise ValidationError("Submitted records cannot be deleted.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Submitted records are immutable.")


class AppendOnly(models.Model):
    objects = ImmutableQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError("Submitted records are immutable; append a correction version.")
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Submitted records cannot be deleted.")
