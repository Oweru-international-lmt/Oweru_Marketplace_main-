from collections.abc import Mapping

from rest_framework import serializers

from apps.lister_identity.serializers import OpaqueEvidenceReferenceField

from .models import PropertyVerification, PropertyVerificationEvidence


class StrictInputSerializer(serializers.Serializer):
    """Reject server-controlled or misspelled input instead of ignoring it."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown = set(data) - set(self.fields)
            if unknown:
                raise serializers.ValidationError({
                    field: "This field is not allowed." for field in sorted(unknown)
                })
        return super().to_internal_value(data)


class DocumentEvidenceInputSerializer(StrictInputSerializer):
    evidence_type = serializers.ChoiceField(
        choices=[PropertyVerificationEvidence.EvidenceType.TITLE_DOCUMENT],
    )
    evidence_ref = OpaqueEvidenceReferenceField()


class FieldEvidenceInputSerializer(StrictInputSerializer):
    evidence_type = serializers.ChoiceField(
        choices=[
            PropertyVerificationEvidence.EvidenceType.FIELD_REPORT,
            PropertyVerificationEvidence.EvidenceType.OFFICIAL_ATTESTATION,
        ],
    )
    evidence_ref = OpaqueEvidenceReferenceField()


class DocumentVerificationSubmissionSerializer(StrictInputSerializer):
    evidence = DocumentEvidenceInputSerializer(many=True, allow_empty=False)


class FieldVerificationSubmissionSerializer(StrictInputSerializer):
    evidence = FieldEvidenceInputSerializer(many=True, allow_empty=False)


class VerificationRejectSerializer(StrictInputSerializer):
    reason = serializers.CharField(max_length=1000, trim_whitespace=True, allow_blank=False)


class EmptyVerificationActionSerializer(StrictInputSerializer):
    pass


class PropertyVerificationPrivateSerializer(serializers.ModelSerializer):
    class Meta:
        model = PropertyVerification
        fields = ("id", "kind", "status", "submitted_at", "reviewed_at", "expires_at")
        read_only_fields = fields


class PropertyVerificationStatusSerializer(serializers.Serializer):
    effective_verification_level = serializers.IntegerField(read_only=True)
    verifications = PropertyVerificationPrivateSerializer(many=True, read_only=True)


class PropertyVerificationReviewSerializer(PropertyVerificationPrivateSerializer):
    property_id = serializers.CharField(source="property.property_id", read_only=True)

    class Meta(PropertyVerificationPrivateSerializer.Meta):
        fields = ("id", "property_id", "kind", "status", "submitted_at", "reviewed_at", "expires_at")
        read_only_fields = fields
