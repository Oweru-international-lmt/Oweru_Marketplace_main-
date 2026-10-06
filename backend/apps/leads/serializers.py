from rest_framework import serializers
from apps.listings.serializers import RejectUnknownFieldsMixin
from .models import Lead, LeadNote, LeadTransition


class LeadSerializer(serializers.ModelSerializer):
    listing_id = serializers.CharField(source="listing.listing_id")
    class Meta:
        model = Lead
        fields = ("id", "listing_id", "buyer_name", "buyer_whatsapp", "source", "stage", "follow_up_at", "created_at", "updated_at")
        read_only_fields = fields


class LeadCreateSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    listing_id = serializers.CharField()
    source = serializers.ChoiceField(choices=Lead.Source.choices)
    buyer_name = serializers.CharField(required=False, max_length=255)
    buyer_whatsapp = serializers.RegexField(r"^\+[1-9]\d{7,14}$", required=False)


class TransitionSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    stage = serializers.ChoiceField(choices=Lead.Stage.choices)
    reason = serializers.CharField(required=False, allow_blank=True, default="")
    final_selling_price = serializers.DecimalField(max_digits=18, decimal_places=0, required=False, min_value=1)


class NoteInputSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    text = serializers.CharField()


class FollowUpSerializer(RejectUnknownFieldsMixin, serializers.Serializer):
    follow_up_at = serializers.DateTimeField(allow_null=True)


class NoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadNote
        fields = ("id", "text", "actor_id", "created_at")
        read_only_fields = fields


class HistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = LeadTransition
        fields = ("from_stage", "to_stage", "actor_id", "reason", "created_at")
        read_only_fields = fields
