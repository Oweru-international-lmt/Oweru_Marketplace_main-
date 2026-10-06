from django.shortcuts import get_object_or_404
from rest_framework.views import APIView
from rest_framework.response import Response
from .models import Lead
from .policies import authorize, lead_scope, require_lister
from .serializers import LeadSerializer, LeadCreateSerializer, TransitionSerializer, NoteInputSerializer, NoteSerializer, FollowUpSerializer, HistorySerializer
from .services import create_lead, LeadTransitionService, add_note, set_follow_up


class LeadCollectionView(APIView):
    def get(self, request):
        actor = authorize(request.user, "lead.view")
        leads = lead_scope(actor, Lead.objects.select_related("listing"))
        return Response(LeadSerializer(leads, many=True).data)

    def post(self, request):
        data = LeadCreateSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        return Response(LeadSerializer(create_lead(actor=request.user, request=request, **data.validated_data)).data, status=201)


class LeadDetailView(APIView):
    def get(self, request, pk):
        actor = authorize(request.user, "lead.view")
        lead = get_object_or_404(lead_scope(actor, Lead.objects.select_related("listing")), pk=pk)
        result = dict(LeadSerializer(lead).data)
        result["notes"] = NoteSerializer(lead.notes.all(), many=True).data
        result["history"] = HistorySerializer(lead.transitions.order_by("created_at"), many=True).data
        return Response(result)


class LeadTransitionView(APIView):
    def post(self, request, pk):
        data = TransitionSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        get_object_or_404(Lead, pk=pk)
        values = data.validated_data
        lead = get_object_or_404(Lead, pk=pk)
        financial = values["stage"] == "CLOSING" or (values["stage"] == "LOST" and hasattr(lead, "deal"))
        if financial:
            from apps.payments.idempotency import execute
            from apps.listings.models import Listing
            from apps.deals.services import lock_deal
            def lock():
                if values["stage"] == "LOST":
                    lock_deal(lead.deal.pk)
                else:
                    Listing.objects.select_for_update().get(pk=lead.listing_id)
                return Lead.objects.select_for_update().get(pk=pk)
            def authorize_transition(row):
                require_lister(request.user, row)
                authorize(request.user, "deal.update")
            result = execute(actor_scope=request.user.pk, operation=f"lead.{values['stage']}", resource=pk, key=request.headers.get("Idempotency-Key"), payload=values, lock=lock, authorize=authorize_transition, mutation=lambda row: dict(LeadSerializer(LeadTransitionService.transition(actor=request.user, lead_id=pk, request=request, **values)).data))
            return Response(result)
        lead = LeadTransitionService.transition(actor=request.user, lead_id=pk, request=request, **values)
        return Response(LeadSerializer(lead).data)


class LeadNoteView(APIView):
    def post(self, request, pk):
        data = NoteInputSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        get_object_or_404(Lead, pk=pk)
        return Response(NoteSerializer(add_note(actor=request.user, lead_id=pk, request=request, **data.validated_data)).data, status=201)


class LeadFollowUpView(APIView):
    def post(self, request, pk):
        data = FollowUpSerializer(data=request.data)
        data.is_valid(raise_exception=True)
        get_object_or_404(Lead, pk=pk)
        return Response(LeadSerializer(set_follow_up(actor=request.user, lead_id=pk, request=request, **data.validated_data)).data)


class CustomersView(APIView):
    def get(self, request):
        actor = authorize(request.user, "lead.view")
        # This endpoint is always a lister's own private customer list.
        leads = Lead.objects.filter(lister=actor).prefetch_related("notes").order_by("buyer_whatsapp", "created_at")
        customers = {}
        for lead in leads:
            item = customers.setdefault(lead.buyer_whatsapp, {"name": lead.buyer_name, "whatsapp": lead.buyer_whatsapp, "leads": []})
            item["leads"].append({"id": str(lead.pk), "stage": lead.stage, "notes": NoteSerializer(lead.notes.all(), many=True).data})
        return Response(list(customers.values()))


class MetricsView(APIView):
    def get(self, request):
        from decimal import Decimal
        actor = authorize(request.user, "lead.view")
        leads = lead_scope(actor, Lead.objects.all()).prefetch_related("transitions")
        if request.query_params.get("listing_id"):
            leads = leads.filter(listing__listing_id=request.query_params["listing_id"])
        counts = {stage: 0 for stage in Lead.Stage.values}
        reached = {stage: 0 for stage in Lead.Stage.values}
        response_seconds = []
        enquiries = 0
        for lead in leads:
            counts[lead.stage] += 1
            enquiries += 1
            history = list(lead.transitions.all())
            stages = {"NEW", *(entry.to_stage for entry in history)}
            for stage in stages:
                reached[stage] += 1
            contacted = [entry.created_at for entry in history if entry.to_stage == "CONTACTED"]
            if contacted:
                response_seconds.append((min(contacted) - lead.created_at).total_seconds())
        conversions = {}
        for start, end in [("NEW", "VIEWING"), ("VIEWING", "CLOSING"), ("CLOSING", "WON")]:
            conversions[f"{start}_to_{end}"] = str(Decimal(reached[end]) / Decimal(reached[start])) if reached[start] else None
        return Response({"enquiries": enquiries, "viewings": reached["VIEWING"], "won_deals": reached["WON"], "stage_counts": counts, "conversion": conversions, "average_response_seconds": sum(response_seconds)/len(response_seconds) if response_seconds else None, "views": None, "views_integration": "M09/M24 event source deferred"})
