from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied
from apps.leads.policies import authorize, management
from apps.leads.services import audit
from apps.listings.serializers import EmptyActionSerializer
from .models import RateTable, RateBand
from .services import publish_rate_table, current_rate_table, save_rate_draft
from .serializers import TableInput


def table_data(table):
    if not table:
        return None
    return {"id": str(table.pk), "version": table.version, "total_rate": str(table.total_rate), "published_at": table.published_at, "bands": [{"lower": str(b.lower), "upper": str(b.upper) if b.upper is not None else None, "oweru_rate": str(b.oweru_rate), "agent_rate": str(b.agent_rate)} for b in table.bands.all()]}


class RateTableView(APIView):
    def get(self, request):
        authorize(request.user, "commission.view")
        return Response(table_data(current_rate_table()))

    @transaction.atomic
    def post(self, request):
        actor = authorize(request.user, "commission.manage")
        if not management(actor):
            raise PermissionDenied("Management required.")
        data = TableInput(data=request.data)
        data.is_valid(raise_exception=True)
        table = save_rate_draft(actor=actor, values=data.validated_data, request=request)
        return Response(table_data(table), status=201)


class RateTableDetailView(APIView):
    def get(self, request, pk):
        actor = authorize(request.user, "commission.view")
        table = get_object_or_404(RateTable, pk=pk)
        if not table.published_at and not management(actor):
            raise PermissionDenied("Only Management can inspect draft rate tables.")
        return Response(table_data(table))

    def put(self, request, pk):
        get_object_or_404(RateTable, pk=pk)
        data = TableInput(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(table_data(save_rate_draft(actor=request.user, table_id=pk, values=data.validated_data, request=request)))


class PublishView(APIView):
    def post(self, request, pk):
        data = EmptyActionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        get_object_or_404(RateTable, pk=pk)
        return Response(table_data(publish_rate_table(actor=request.user, table_id=pk, request=request)))
