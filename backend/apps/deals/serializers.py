from rest_framework import serializers
from .models import Deal
from apps.payments.services import payment_status


class DealSerializer(serializers.ModelSerializer):
    listing_id = serializers.CharField(source="listing.listing_id")
    payment_status = serializers.SerializerMethodField()
    class Meta:
        model = Deal
        fields = ("id", "lead_id", "listing_id", "buyer_name", "lister_kind", "owner_price", "final_selling_price", "rate_table_id", "rate_band_id", "buyer_to_owner", "buyer_to_oweru", "oweru_keeps", "agent_payout", "state", "payment_status", "agreement_price_confirmed_at", "agreement_approved_at", "completed_at", "created_at")
        read_only_fields = fields

    def get_payment_status(self, obj):
        return payment_status(obj)


class BuyerDealSerializer(DealSerializer):
    class Meta(DealSerializer.Meta):
        fields = tuple(field for field in DealSerializer.Meta.fields if field not in {"owner_price", "oweru_keeps", "agent_payout", "rate_table_id", "rate_band_id"})
