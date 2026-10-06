from decimal import Decimal
from rest_framework import serializers
from apps.listings.serializers import RejectUnknownFieldsMixin


class BandInput(RejectUnknownFieldsMixin, serializers.Serializer):
    lower = serializers.DecimalField(max_digits=18, decimal_places=0, min_value=0)
    upper = serializers.DecimalField(max_digits=18, decimal_places=0, min_value=0, allow_null=True)
    oweru_rate = serializers.DecimalField(max_digits=7, decimal_places=6, min_value=0, max_value=Decimal("0.999999"))
    agent_rate = serializers.DecimalField(max_digits=7, decimal_places=6, min_value=0, max_value=Decimal("0.999999"))


class TableInput(RejectUnknownFieldsMixin, serializers.Serializer):
    version = serializers.IntegerField(min_value=1)
    total_rate = serializers.DecimalField(max_digits=7, decimal_places=6, min_value=Decimal("0.000001"), max_value=Decimal("0.999999"))
    bands = BandInput(many=True, allow_empty=False)
