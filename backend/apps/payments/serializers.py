from rest_framework import serializers
from apps.listings.serializers import RejectUnknownFieldsMixin


class BankSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    bank_name = serializers.CharField(max_length=255)
    account_name = serializers.CharField(max_length=255)
    account_number = serializers.CharField(max_length=100)
    branch = serializers.CharField(max_length=255)


class ProofSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    transfer = serializers.ChoiceField(choices=["OWNER", "OWERU"])
    file = serializers.FileField()


class ReceiptSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    bank_reference = serializers.CharField(max_length=255)


class TaxSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    number = serializers.CharField(max_length=255)
    kind = serializers.ChoiceField(choices=["EFD", "VFD"])
    file = serializers.FileField()


class AgreementSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    file = serializers.FileField()


class ExactPriceSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    confirms_exact_final_price = serializers.BooleanField()

    def validate_confirms_exact_final_price(self, value):
        if not value:
            raise serializers.ValidationError("Explicit exact final price confirmation is required.")
        return value


class PayoutPaidSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    bank_reference = serializers.CharField(max_length=255)
    file = serializers.FileField()


class HoldSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    reason = serializers.CharField()


class RequestConfirmationSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    purpose = serializers.ChoiceField(choices=["PHONE", "OWNER_PRICE", "OWNER_RECEIPT"])
    listing_id = serializers.CharField(required=False)
    deal_id = serializers.UUIDField(required=False)
    owner_name = serializers.CharField(required=False, max_length=255)
    owner_whatsapp = serializers.RegexField(r"^\+[1-9]\d{7,14}$", required=False)


class DecisionSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    token = serializers.CharField()
    decision = serializers.ChoiceField(choices=["CONFIRM", "DECLINE"])
    bank = BankSerializer(required=False)
    bank_reference = serializers.CharField(required=False, allow_blank=True, max_length=255)
