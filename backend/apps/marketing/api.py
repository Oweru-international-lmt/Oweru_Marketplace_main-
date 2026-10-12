from django.http import HttpResponseRedirect
from django.utils import timezone
from django.urls import path
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.throttling import AnonRateThrottle
from drf_spectacular.utils import extend_schema, OpenApiParameter
from drf_spectacular.types import OpenApiTypes
from apps.properties.serializers import RejectUnknownFieldsMixin
from . import services
from .models import Content, FeaturedListing, MarketingConsent


class ConsentInput(RejectUnknownFieldsMixin, serializers.Serializer):
    agreed = serializers.BooleanField()
    policy_version = serializers.CharField(max_length=100)
    version = serializers.IntegerField(min_value=0)


class ConsentView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: OpenApiTypes.OBJECT}, description="Own marketing consent and current version; default is opted out.")
    def get(self, request):
        actor = services.authorize(request.user, "account.view")
        row = MarketingConsent.objects.filter(user=actor).first()
        return Response({"agreed": row.agreed if row else False, "version": row.version if row else 0})

    @extend_schema(request=ConsentInput, responses={200: OpenApiTypes.OBJECT})
    def put(self, request):
        data = ConsentInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = services.consent(actor=request.user, **data.validated_data)
        return Response({"agreed": row.agreed, "version": row.version})


class PeriodInput(RejectUnknownFieldsMixin, serializers.Serializer):
    starts_at = serializers.DateTimeField()
    ends_at = serializers.DateTimeField()
    enabled = serializers.BooleanField(default=True)
    version = serializers.IntegerField(min_value=0)


class FeaturedInput(PeriodInput):
    listing_id = serializers.CharField(max_length=50)


class CampaignInput(RejectUnknownFieldsMixin, serializers.Serializer):
    subject_en = serializers.CharField(max_length=200)
    subject_sw = serializers.CharField(max_length=200)
    body_en = serializers.CharField(max_length=10000)
    body_sw = serializers.CharField(max_length=10000)
    target_path = serializers.CharField(max_length=500)
    source_tag = serializers.SlugField(max_length=100)


class ContentInput(PeriodInput):
    slug = serializers.SlugField(max_length=50)
    kind = serializers.ChoiceField(choices=["BANNER", "PAGE"])
    title_en = serializers.CharField(max_length=200)
    title_sw = serializers.CharField(max_length=200)
    body_en = serializers.CharField(max_length=10000)
    body_sw = serializers.CharField(max_length=10000)
    target_path = serializers.CharField(max_length=500)
    source_tag = serializers.SlugField(max_length=100)


class ItemView(APIView):
    permission_classes = [IsAuthenticated]
    model = Content
    input_class = ContentInput

    @extend_schema(responses={200: {"type": "array", "items": {"type": "object"}}})
    def get(self, request, item_id=None):
        services.staff(request.user)
        rows = self.model.objects.order_by("-created_at")
        return Response(list(rows.values()[:100]))

    @extend_schema(request=ContentInput, responses={200: OpenApiTypes.OBJECT, 201: OpenApiTypes.OBJECT})
    def post(self, request, item_id=None):
        services.staff(request.user)
        data = self.input_class(data=request.data)
        data.is_valid(raise_exception=True)
        values = dict(data.validated_data)
        version = values.pop("version")
        row = services.save_item(actor=request.user, model=self.model, values=values, version=version, item_id=item_id, request=request)
        return Response({"id": str(row.pk), "version": row.version}, status=200 if item_id else 201)


class FeaturedView(ItemView):
    model = FeaturedListing
    input_class = FeaturedInput

    @extend_schema(request=FeaturedInput, responses={200: OpenApiTypes.OBJECT, 201: OpenApiTypes.OBJECT})
    def post(self, request, item_id=None):
        return super().post(request, item_id)


class CampaignView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(responses={200: {"type": "array", "items": {"type": "object"}}}, description="Non-personal campaign delivery and click counts, at most 100 campaigns.")
    def get(self, request):
        return Response(services.results(request.user))

    @extend_schema(request=CampaignInput, responses={201: OpenApiTypes.OBJECT}, description="Queue a bilingual campaign for active opted-in recipients; workers recheck consent before SMTP submission.")
    def post(self, request):
        services.staff(request.user, "marketing.send_campaign")
        data = CampaignInput(data=request.data)
        data.is_valid(raise_exception=True)
        row = services.create_campaign(actor=request.user, values=dict(data.validated_data), request=request)
        return Response({"id": str(row.pk), "recipients": row.deliveries.count()}, status=201)


class PublicView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(parameters=[OpenApiParameter("language", OpenApiTypes.STR, enum=["sw", "en"])], responses={200: OpenApiTypes.OBJECT})
    def get(self, request):
        language = request.query_params.get("language", "sw")
        if language not in {"sw", "en"}:
            raise serializers.ValidationError("Unsupported language.")
        now = timezone.now()
        content = Content.objects.filter(enabled=True, starts_at__lte=now, ends_at__gt=now).order_by("slug")[:100]
        from apps.listings.services import get_public_listings
        featured = get_public_listings().filter(pk__in=FeaturedListing.objects.filter(enabled=True, starts_at__lte=now, ends_at__gt=now).values("listing_id"))
        return Response({"content": [{"slug": row.slug, "kind": row.kind, "title": getattr(row, "title_" + language), "body": getattr(row, "body_" + language), "link": services.tagged_link(row.target_path, row.source_tag)} for row in content], "featured": [{"listing_id": row.listing_id, "link": services.tagged_link("/listings/" + row.listing_id, "featured")} for row in featured[:100]]})


class ClickView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle]

    @extend_schema(parameters=[OpenApiParameter("token", OpenApiTypes.STR, required=True)], responses={302: None})
    def get(self, request):
        response = HttpResponseRedirect(services.click(request.query_params.get("token", "")))
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response


urlpatterns = [path("", PublicView.as_view()), path("consent/", ConsentView.as_view()), path("click/", ClickView.as_view()), path("staff/content/", ItemView.as_view()), path("staff/content/<uuid:item_id>/", ItemView.as_view()), path("staff/featured/", FeaturedView.as_view()), path("staff/featured/<uuid:item_id>/", FeaturedView.as_view()), path("staff/campaigns/", CampaignView.as_view())]
