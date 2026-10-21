from rest_framework import serializers
from .models import Deal
from apps.payments.services import payment_status


def _proof_rows(deal):
    return [{"transfer": proof.transfer, "media_id": proof.media.media_id, "uploaded_at": proof.created_at} for proof in deal.payment_proofs.select_related("media").order_by("created_at")]


class DealSerializer(serializers.ModelSerializer):
    """The lister's view. Slips stay with the buyer and management (M13)."""

    listing_id = serializers.CharField(source="listing.listing_id")
    lister_name = serializers.CharField(source="lister.full_name")
    payment_status = serializers.SerializerMethodField()
    property = serializers.SerializerMethodField()
    steps = serializers.SerializerMethodField()
    agreement_media_id = serializers.SerializerMethodField()
    tax_receipt = serializers.SerializerMethodField()
    payout = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = ("id", "lead_id", "listing_id", "buyer_name", "lister_name", "lister_kind", "owner_price", "final_selling_price", "rate_table_id", "rate_band_id", "buyer_to_owner", "buyer_to_oweru", "oweru_keeps", "agent_payout", "payment_reference", "state", "payment_status", "property", "steps", "agreement_media_id", "agreement_price_confirmed_at", "agreement_approved_at", "tax_receipt", "payout", "completed_at", "created_at")
        read_only_fields = fields

    def get_payment_status(self, obj):
        return payment_status(obj)

    def get_property(self, obj):
        # Type and area only: deal pages never carry the exact pin.
        from apps.verification.review_desk import _photos
        record = obj.property
        area = ", ".join(part.name for part in (record.ward, record.district, record.region) if part is not None)
        photos = _photos(obj.listing, limit=1)
        return {"property_id": record.property_id, "category": record.category, "area": area, "cover_url": photos[0]["url"] if photos else None}

    def get_steps(self, obj):
        # When each SRD 9.5 step happened, for the deal timeline.
        proofs = {}
        for proof in obj.payment_proofs.order_by("created_at"):
            proofs.setdefault(proof.transfer, proof.created_at)
        confirmed = {row.transfer: row.created_at for row in obj.payment_confirmations.all()}
        receipt = getattr(obj, "tax_receipt", None)
        return {
            "created_at": obj.created_at,
            "owner_paid_at": proofs.get("OWNER"),
            "oweru_paid_at": proofs.get("OWERU"),
            "owner_confirmed_at": confirmed.get("OWNER"),
            "oweru_confirmed_at": confirmed.get("OWERU"),
            "agreement_uploaded_at": obj.agreement.created_at if obj.agreement_id else None,
            "agreement_price_confirmed_at": obj.agreement_price_confirmed_at,
            "agreement_approved_at": obj.agreement_approved_at,
            "tax_receipt_at": receipt.created_at if receipt else None,
            "completed_at": obj.completed_at,
        }

    def get_agreement_media_id(self, obj):
        return obj.agreement.media_id if obj.agreement_id else None

    def get_tax_receipt(self, obj):
        receipt = getattr(obj, "tax_receipt", None)
        return {"number": receipt.number, "kind": receipt.kind, "media_id": receipt.media.media_id, "recorded_at": receipt.created_at} if receipt else None

    def get_payout(self, obj):
        payout = getattr(obj, "payout", None)
        if payout is None:
            return None
        return {"status": payout.status, "amount": str(payout.amount), "due_at": payout.due_at, "paid_at": payout.paid_at, "hold_reason": payout.hold_reason, "bank_reference": payout.bank_reference, "proof_media_id": payout.proof.media_id if payout.proof_id else None}


class BuyerDealSerializer(DealSerializer):
    """The buyer's view: their own slips, no commission split or payout."""

    proofs = serializers.SerializerMethodField()

    class Meta(DealSerializer.Meta):
        fields = tuple(field for field in DealSerializer.Meta.fields if field not in {"owner_price", "oweru_keeps", "agent_payout", "rate_table_id", "rate_band_id", "payout"}) + ("proofs",)

    def get_proofs(self, obj):
        return _proof_rows(obj)


class ManagementDealSerializer(DealSerializer):
    """Management's review view: slips, receiving banks and confirmation references (PAY-05)."""

    proofs = serializers.SerializerMethodField()
    confirmations = serializers.SerializerMethodField()
    banks = serializers.SerializerMethodField()

    class Meta(DealSerializer.Meta):
        fields = DealSerializer.Meta.fields + ("buyer_whatsapp", "proofs", "confirmations", "banks")

    def get_proofs(self, obj):
        return _proof_rows(obj)

    def get_confirmations(self, obj):
        return [{"transfer": row.transfer, "amount": str(row.amount), "bank_reference": row.bank_reference, "by_owner_link": row.delivery_id is not None, "confirmed_at": row.created_at} for row in obj.payment_confirmations.order_by("created_at")]

    def get_banks(self, obj):
        return {"owner": obj.owner_bank_snapshot, "oweru": obj.oweru_bank_snapshot}
