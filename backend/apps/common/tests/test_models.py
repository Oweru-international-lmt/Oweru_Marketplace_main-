import uuid

from apps.common.models import CreatedByModel, TimeStampedModel, UUIDModel


def test_common_models_are_abstract():
    assert UUIDModel._meta.abstract
    assert TimeStampedModel._meta.abstract
    assert CreatedByModel._meta.abstract


def test_uuid_model_defines_uuid_primary_key():
    field = UUIDModel._meta.get_field("id")

    assert field.primary_key
    assert field.default == uuid.uuid4
