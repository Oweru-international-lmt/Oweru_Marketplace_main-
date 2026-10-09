from urllib.parse import quote
from decimal import Decimal
from django.conf import settings
from django.utils import timezone
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from apps.properties.serializers import RejectUnknownFieldsMixin, GeoJSONPointField
from apps.properties.models import PropertyRecord
from apps.media.storage import get_private_media_storage
from . import services


class CheckInput(RejectUnknownFieldsMixin, serializers.Serializer):
    pin = GeoJSONPointField()
    category = serializers.ChoiceField(choices=PropertyRecord.Category.choices)
    size = serializers.DecimalField(max_digits=18, decimal_places=2, min_value=Decimal("0.01"))
    size_unit = serializers.ChoiceField(choices=["sqm", "acres", "hectares"])
    description = serializers.CharField(max_length=4000)
    phone = serializers.CharField(max_length=30)
    email = serializers.EmailField(required=False, allow_blank=True)
    language = serializers.ChoiceField(choices=["sw", "en"], default="sw")
    external_url = serializers.URLField(max_length=1000, required=False, allow_blank=True)

    def validate_description(self, value):
        # Exact geometry and internal methods cannot be reflected into shareable reports.
        import re
        if re.search(r"(?:coordinates|boundary|polygon|latitude|longitude|\bpin\b|\bGPS\b)", value, re.I) or re.search(r"[-+]?\d{1,3}\.\d+\s*[,; ]\s*[-+]?\d{1,3}\.\d+", value):
            raise serializers.ValidationError("Describe the property without exact coordinates or boundaries.")
        return value


class SubmitView(APIView):
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    def post(self, request):
        values = request.data.copy()
        if "photos" in values:
            values.pop("photos")
        check = services.submit(values=values, key=request.headers.get("Idempotency-Key"), photos=request.FILES.getlist("photos"), actor=request.user, request=request)
        path = f"/api/v1/free-checks/{check.pk}/?token={services.token_for(check)}"
        link = request.build_absolute_uri(path)
        return Response({**services.public_result(check), "report_link": link, "download_path": path.replace("/?", "/pdf/?"), "whatsapp_link": f"https://wa.me/{check.phone.lstrip('+')}?text={quote(link)}"}, status=201)


class ReportView(APIView):
    permission_classes = [AllowAny]

    def finalize_response(self, request, response, *args, **kwargs):
        response = super().finalize_response(request, response, *args, **kwargs)
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response

    def get(self, request, check_id, pdf=False):
        check = services.authorized_check(check_id, request.query_params.get("token"), request)
        if not pdf:
            return Response(services.public_result(check))
        report = check.reports.order_by("-version").first()
        remaining = max(1, int((check.expires_at - timezone.now()).total_seconds()))
        url = get_private_media_storage().generate_signed_read_url(key=report.media.file_key, expires_in=min(settings.MEDIA_SIGNED_URL_TTL_SECONDS, remaining))
        response = Response({"url": url, "reference": check.reference})
        response["Cache-Control"] = "no-store"
        response["Referrer-Policy"] = "no-referrer"
        return response
