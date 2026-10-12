from datetime import timedelta
from django.http import HttpResponse
from django.urls import path
from django.utils import timezone
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from drf_spectacular.utils import extend_schema
from drf_spectacular.types import OpenApiTypes
from apps.properties.serializers import RejectUnknownFieldsMixin
from . import services
from .export import workbook


class PanelInput(RejectUnknownFieldsMixin, serializers.Serializer):
    start = serializers.DateField(required=False)
    end = serializers.DateField(required=False)
    region = serializers.UUIDField(required=False)
    district = serializers.UUIDField(required=False)
    category = serializers.ChoiceField(choices=["LAND", "HOUSE", "COMMERCIAL"], required=False)
    kind = serializers.ChoiceField(choices=["STOCK", "ACTIVITY", "COVERAGE", "MONTHLY"], required=False)

    def validate(self, values):
        values.setdefault("end", timezone.localdate())
        values.setdefault("start", values["end"] - timedelta(days=29))
        if values["end"] < values["start"] or (values["end"] - values["start"]).days > 365:
            raise serializers.ValidationError("Choose an ordered date range of at most 366 days.")
        return values


class PanelView(APIView):
    export = False

    @extend_schema(parameters=[PanelInput], responses={200: OpenApiTypes.OBJECT}, description="Non-personal precomputed daily activity/stock/coverage or calendar-month price snapshots. At most 10,000 cells.")
    def get(self, request):
        services.staff(request.user, "analytics.export" if self.export else "analytics.view")
        data = PanelInput(data=request.query_params)
        data.is_valid(raise_exception=True)
        result = services.panel(actor=request.user, filters=data.validated_data, export=self.export, request=request)
        if not self.export:
            response = Response(result)
        else:
            response = HttpResponse(workbook(result["rows"]), content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            response["Content-Disposition"] = 'attachment; filename="market-monitoring.xlsx"'
        response["Cache-Control"] = "no-store"
        return response


class ExportView(PanelView):
    export = True

    @extend_schema(parameters=[PanelInput], responses={200: OpenApiTypes.BINARY}, description="Excel export of the same filtered monitoring cells. Text values are never formulas.")
    def get(self, request):
        return super().get(request)


urlpatterns = [path("", PanelView.as_view()), path("export/", ExportView.as_view())]
