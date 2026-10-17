"""The verifier's location check desk (VER-02): one screen per property.

Payloads never carry private evidence references or storage keys. Photos and
the title document are opened through short-lived links, and opening the
document is recorded as sensitive access.
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, Q
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import generics, serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import record_sensitive_access
from apps.listings.models import Listing, ListingPhoto
from apps.media.models import Media, MediaVariant
from apps.media.storage import get_private_media_storage
from apps.properties.models import PossibleDuplicate, PropertyRecord
from apps.roles.permissions import IsVerifier

from .models import PropertyVerification, PropertyVerificationEvidence
from .serializers import StrictInputSerializer
from .services import LOCATION_CHECKLIST

# A check waiting longer than this shows as late on the desk.
LATE_AFTER = timedelta(days=2)


def _latest_listing(property_record):
    return Listing.objects.filter(property=property_record).order_by("-created_at").first()


def _signed_display_url(media):
    variant = media.variants.filter(kind=MediaVariant.Kind.DISPLAY).first()
    key = variant.file_key if variant else media.file_key
    try:
        return get_private_media_storage().generate_signed_read_url(
            key=key, expires_in=settings.MEDIA_SIGNED_URL_TTL_SECONDS
        )
    except Exception:  # noqa: BLE001 - a missing object just shows no photo
        return None


def _photos(listing, limit=None):
    if listing is None:
        return []
    photos = []
    for row in ListingPhoto.objects.filter(listing=listing).select_related("media").order_by("position"):
        url = _signed_display_url(row.media)
        if url:
            photos.append({"position": row.position, "url": url})
        if limit and len(photos) == limit:
            break
    return photos


def _cover_url(property_record):
    photos = _photos(_latest_listing(property_record), limit=1)
    return photos[0]["url"] if photos else None


def _area(property_record):
    parts = [getattr(property_record, name) for name in ("locality", "ward", "district", "region")]
    return ", ".join(part.name for part in parts if part is not None)


def _duplicates(property_record):
    return PossibleDuplicate.objects.filter(
        Q(property_a=property_record) | Q(property_b=property_record)
    ).select_related("property_a", "property_b", "property_a__locality", "property_b__locality",
                     "property_a__ward", "property_b__ward", "property_a__district", "property_b__district",
                     "property_a__region", "property_b__region")


def _point(geometry):
    return {"lat": geometry.y, "lng": geometry.x} if geometry is not None else None


class DocumentQueueRowSerializer(serializers.ModelSerializer):
    property_id = serializers.CharField(source="property.property_id", read_only=True)
    category = serializers.CharField(source="property.category", read_only=True)
    title_type = serializers.CharField(source="property.title_type", read_only=True)
    stated_size = serializers.DecimalField(source="property.stated_size", max_digits=18, decimal_places=2, read_only=True)
    size_unit = serializers.CharField(source="property.size_unit", read_only=True)
    area = serializers.SerializerMethodField()
    lister_name = serializers.CharField(source="submitted_by.full_name", read_only=True)
    cover_url = serializers.SerializerMethodField()
    duplicate_count = serializers.SerializerMethodField()
    late = serializers.SerializerMethodField()

    class Meta:
        model = PropertyVerification
        fields = (
            "id", "property_id", "kind", "status", "submitted_at", "reviewed_at", "expires_at",
            "category", "title_type", "stated_size", "size_unit", "area", "lister_name",
            "cover_url", "duplicate_count", "late",
        )
        read_only_fields = fields

    def get_area(self, obj):
        return _area(obj.property)

    def get_cover_url(self, obj):
        return _cover_url(obj.property)

    def get_duplicate_count(self, obj):
        return _duplicates(obj.property).exclude(status=PossibleDuplicate.Status.NOT_DUPLICATE).count()

    def get_late(self, obj):
        return obj.status == PropertyVerification.Status.PENDING and obj.submitted_at < timezone.now() - LATE_AFTER


class DocumentDeskSerializer(DocumentQueueRowSerializer):
    """Everything the location check screen shows, without private references."""

    reason = serializers.CharField(source="rejection_reason", read_only=True, allow_null=True)
    reviewer_name = serializers.SerializerMethodField()
    pin = serializers.SerializerMethodField()
    boundary = serializers.SerializerMethodField()
    listing = serializers.SerializerMethodField()
    documents = serializers.SerializerMethodField()
    duplicates = serializers.SerializerMethodField()
    checklist = serializers.SerializerMethodField()

    class Meta(DocumentQueueRowSerializer.Meta):
        fields = DocumentQueueRowSerializer.Meta.fields + (
            "reason", "reviewer_name", "pin", "boundary", "listing", "documents", "duplicates", "checklist",
        )
        read_only_fields = fields

    def get_reviewer_name(self, obj):
        return obj.reviewed_by.full_name if obj.reviewed_by_id else None

    def get_pin(self, obj):
        return _point(obj.property.pin)

    def get_boundary(self, obj):
        boundary = obj.property.boundary
        return [{"lat": lat, "lng": lng} for lng, lat in boundary.coords[0]] if boundary else None

    def get_listing(self, obj):
        listing = _latest_listing(obj.property)
        if listing is None:
            return None
        return {
            "listing_id": listing.listing_id,
            "status": listing.status,
            "lister_kind": listing.lister_kind,
            "description": listing.description,
            "features": listing.features,
            "photo_count": listing.photos.count(),
        }

    def get_documents(self, obj):
        return [
            {"id": str(item.pk), "evidence_type": item.evidence_type, "created_at": item.created_at}
            for item in obj.evidence.order_by("created_at", "id")
        ]

    def get_duplicates(self, obj):
        rows = []
        for duplicate in _duplicates(obj.property):
            other = duplicate.property_b if duplicate.property_a_id == obj.property_id else duplicate.property_a
            rows.append({
                "id": str(duplicate.pk),
                "property_id": other.property_id,
                "status": duplicate.status,
                "signals": duplicate.signals,
                "distance_meters": duplicate.distance_meters,
                "size_difference_percent": duplicate.size_difference_percent,
                "category": other.category,
                "stated_size": other.stated_size,
                "size_unit": other.size_unit,
                "area": _area(other),
                "pin": _point(other.pin),
                "cover_url": _cover_url(other),
            })
        return rows

    def get_checklist(self, obj):
        return list(LOCATION_CHECKLIST)


def document_queue(state):
    queryset = PropertyVerification.objects.select_related(
        "property", "property__locality", "property__ward", "property__district", "property__region", "submitted_by",
    ).filter(kind=PropertyVerification.Kind.DOCUMENT)
    if state == "decided":
        return queryset.filter(
            status__in=[PropertyVerification.Status.APPROVED, PropertyVerification.Status.REJECTED],
        ).order_by("-reviewed_at", "-id")
    return queryset.filter(status=PropertyVerification.Status.PENDING).order_by("submitted_at", "id")


class DocumentApproveSerializer(StrictInputSerializer):
    checklist = serializers.DictField(child=serializers.BooleanField(), required=False)


class DocumentRejectSerializer(StrictInputSerializer):
    reason = serializers.CharField(max_length=1000, trim_whitespace=True, allow_blank=False)
    checklist = serializers.DictField(child=serializers.BooleanField(), required=False)


class DocumentSummaryView(generics.GenericAPIView):
    """The four counts above the queue (C2)."""

    permission_classes = [IsAuthenticated, IsVerifier]

    @extend_schema(responses={200: {"type": "object"}})
    def get(self, request, *args, **kwargs):
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        rows = PropertyVerification.objects.filter(kind=PropertyVerification.Kind.DOCUMENT)
        pending = Q(status=PropertyVerification.Status.PENDING)
        counts = rows.aggregate(
            waiting=Count("id", filter=pending),
            late=Count("id", filter=pending & Q(submitted_at__lt=now - LATE_AFTER)),
            passed_this_month=Count("id", filter=Q(status=PropertyVerification.Status.APPROVED, reviewed_at__gte=month_start)),
            failed_this_month=Count("id", filter=Q(status=PropertyVerification.Status.REJECTED, reviewed_at__gte=month_start)),
        )
        return Response(counts)


class DocumentPhotosView(generics.GenericAPIView):
    """Short-lived links to the listing photos of the property under check."""

    permission_classes = [IsAuthenticated, IsVerifier]

    def get(self, request, verification_id, *args, **kwargs):
        verification = _document_or_404(verification_id)
        return Response(_photos(_latest_listing(verification.property)))


class DocumentEvidenceView(generics.GenericAPIView):
    """A short-lived link to one title document, recorded as sensitive access."""

    permission_classes = [IsAuthenticated, IsVerifier]

    def get(self, request, verification_id, evidence_id, *args, **kwargs):
        verification = _document_or_404(verification_id)
        evidence = PropertyVerificationEvidence.objects.filter(verification=verification, pk=evidence_id).first()
        if evidence is None:
            raise NotFound("Document was not found.")
        media = Media.objects.filter(
            media_id=evidence.evidence_ref,
            content_type=ContentType.objects.get_for_model(PropertyRecord),
            object_id=verification.property_id,
        ).first()
        if media is None:
            raise NotFound("Document file was not found.")
        record_sensitive_access(
            actor=request.user,
            entity_type="PropertyVerification",
            entity_id=verification.pk,
            after={"access_type": "verification_title_document", "purpose": "location_check", "evidence": str(evidence.pk)},
            request=request,
        )
        expires_in = settings.MEDIA_SIGNED_URL_TTL_SECONDS
        url = get_private_media_storage().generate_signed_read_url(key=media.file_key, expires_in=expires_in)
        return Response({"url": url, "expires_in": expires_in, "mime_type": media.mime_type})


def _document_or_404(verification_id):
    try:
        return PropertyVerification.objects.select_related("property").get(
            pk=verification_id, kind=PropertyVerification.Kind.DOCUMENT
        )
    except (TypeError, ValueError, PropertyVerification.DoesNotExist) as exc:
        raise NotFound("Property verification was not found.") from exc
