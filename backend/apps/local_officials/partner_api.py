"""Management of local officials (LOC-01, LOC-06, LOC-07) and the public registration link (SRD 14.2)."""
from collections import defaultdict

from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, serializers, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.audit.services import create_audit_log
from apps.localities.models import District, Locality, Region, Ward
from apps.media import storage as media_storage
from apps.professionals.models import ProfessionalProfile
from apps.verification.models import VerificationTask

from .full_check import coverage_manager
from .models import LocalOfficialInvite, LocalOfficialProfile, OfficialLocalityCoverage
from .registration import approve_official, cancel_invite, deactivate_official, invite_official, live_invite, register_official, resend_invite, send_invite
from .serializers import StrictInputSerializer


def _place(locality):
    if locality is None:
        return None
    ward = locality.ward
    return {"id": str(locality.pk), "name": locality.name, "kind": locality.kind, "ward": ward.name, "district": ward.district.name, "region": ward.district.region.name}


def _mask(value):
    value = value or ""
    return ("•" * max(0, len(value) - 4) + value[-4:]) if value else ""


def _manager(request):
    with transaction.atomic():
        return coverage_manager(request.user)


def official_row(profile):
    user = profile.user
    documents = sum(bool(item) for item in (profile.photo_id, profile.stamp_photo_id, profile.national_id_number))
    covered = [row.locality.name for row in profile.locality_coverage.all() if row.revoked_at is None]
    return {
        "official_id": profile.official_id, "name": user.full_name, "phone": user.phone if user.phone.startswith("+") and "~" not in user.phone else "",
        "email": user.email, "position": profile.position, "status": profile.status,
        "national_id": _mask(profile.national_id_number), "locality": _place(profile.locality), "covers": covered,
        "documents": {"received": documents, "total": 3},
        "has_photo": bool(profile.photo_id), "has_stamp": bool(profile.stamp_photo_id),
        "confirmed_by": profile.confirmed_by.full_name if profile.confirmed_by_id else "", "confirmed_at": profile.confirmed_at,
        "deactivated_reason": profile.deactivated_reason, "created_at": profile.created_at,
    }


def invite_row(invite):
    return {
        "id": str(invite.pk), "locality": _place(invite.locality), "phone": invite.phone, "status": invite.status,
        "expires_at": invite.expires_at, "created_at": invite.created_at, "invited_by": invite.invited_by.full_name,
        "replaces": {"official_id": invite.replaces.official_id, "name": invite.replaces.user.full_name} if invite.replaces_id else None,
    }


class InviteInput(StrictInputSerializer):
    locality = serializers.PrimaryKeyRelatedField(queryset=Locality.objects.filter(approved=True))
    phone = serializers.CharField(max_length=30)


class DeactivateInput(StrictInputSerializer):
    reason = serializers.CharField(max_length=1000)
    replacement_phone = serializers.CharField(max_length=30, required=False, allow_blank=True)


class OfficialListView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        _manager(request)
        profiles = LocalOfficialProfile.objects.select_related("user", "confirmed_by", "locality__ward__district__region").prefetch_related("locality_coverage__locality").order_by("-created_at")
        return Response([official_row(profile) for profile in profiles])


class InviteCollectionView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InviteInput

    def get(self, request):
        _manager(request)
        rows = LocalOfficialInvite.objects.select_related("locality__ward__district__region", "invited_by", "replaces__user").filter(used_at__isnull=True, cancelled_at__isnull=True)
        return Response([invite_row(row) for row in rows])

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invite, token = invite_official(actor=request.user, request=request, **serializer.validated_data)
        return Response({**invite_row(invite), "delivery": send_invite(invite, token, request.user)}, status=status.HTTP_201_CREATED)


class InviteResendView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, invite_id):
        invite, token = resend_invite(actor=request.user, invite_id=invite_id, request=request)
        return Response({**invite_row(invite), "delivery": send_invite(invite, token, request.user)})


class InviteCancelView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, invite_id):
        return Response(invite_row(cancel_invite(actor=request.user, invite_id=invite_id, request=request)))


class OfficialApproveView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, official_id):
        profile = approve_official(actor=request.user, official_id=official_id, request=request)
        return Response(official_row(LocalOfficialProfile.objects.select_related("user", "confirmed_by", "locality__ward__district__region").get(pk=profile.pk)))


class OfficialDeactivateView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = DeactivateInput

    @transaction.atomic
    def post(self, request, official_id):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = deactivate_official(actor=request.user, official_id=official_id, reason=serializer.validated_data["reason"], request=request)
        body = {"official": official_row(LocalOfficialProfile.objects.select_related("user", "confirmed_by", "locality__ward__district__region").get(pk=profile.pk))}
        phone = serializer.validated_data.get("replacement_phone", "").strip()
        if phone:
            if profile.locality_id is None:
                from rest_framework.exceptions import ValidationError
                raise ValidationError({"replacement_phone": "This official has no registered street or village to replace."})
            invite, token = invite_official(actor=request.user, locality=profile.locality_id, phone=phone, replaces=profile, request=request)
            body["invite"] = {**invite_row(invite), "delivery": send_invite(invite, token, request.user)}
        return Response(body)


class OfficialPhotoView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, official_id, kind):
        actor = _manager(request)
        profile = get_object_or_404(LocalOfficialProfile.objects.select_related("photo", "stamp_photo"), official_id=official_id)
        media = {"photo": profile.photo, "stamp": profile.stamp_photo}.get(kind)
        if media is None:
            return Response({"detail": "Not found."}, status=404)
        try:
            url = media_storage.get_private_media_storage().generate_signed_read_url(key=media.file_key)
        except Exception:
            return Response({"detail": "The photo is not available."}, status=404)
        create_audit_log(actor=actor, action="sensitive_data.accessed", entity_type="LocalOfficialProfile", entity_id=profile.pk, after={"purpose": f"official_{kind}"}, request=request)
        return Response({"url": url})


class CoverageView(generics.GenericAPIView):
    """LOC-07: streets, villages and wards with active officials, plus professionals covering each area."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        _manager(request)
        now = timezone.now()
        region, district, ward = (request.query_params.get(key) for key in ("region", "district", "ward"))
        localities = Locality.objects.filter(approved=True).select_related("ward__district__region")
        live = OfficialLocalityCoverage.objects.filter(revoked_at__isnull=True, starts_at__lte=now, official__is_active=True, official__status="ACTIVE").filter(Q(expires_at__isnull=True) | Q(expires_at__gt=now))
        officials_by_locality = defaultdict(set)
        for locality_id, official_id in live.values_list("locality_id", "official_id"):
            officials_by_locality[locality_id].add(official_id)
        waiting = defaultdict(int)
        for locality_id in VerificationTask.objects.filter(kind="LOCAL_OFFICE", status="NEEDS_OFFICIAL", job__status="IN_PROGRESS").values_list("job__property__locality_id", flat=True):
            waiting[locality_id] += 1
        pros = list(ProfessionalProfile.objects.filter(status="ACTIVE").prefetch_related("regions", "districts"))
        district_region = dict(District.objects.values_list("pk", "region_id"))

        if ward:
            parent = get_object_or_404(Ward.objects.select_related("district__region"), pk=ward)
            level, crumbs = "locality", [parent.district.region, parent.district, parent]
            groups = {row.pk: (row.name, [row]) for row in localities.filter(ward=parent)}
            pro_area = ("district", parent.district_id)
        elif district:
            parent = get_object_or_404(District.objects.select_related("region"), pk=district)
            level, crumbs = "ward", [parent.region, parent]
            groups = {row.pk: (row.name, []) for row in Ward.objects.filter(district=parent)}
            for row in localities.filter(ward__district=parent):
                groups[row.ward_id][1].append(row)
            pro_area = ("district", parent.pk)
        elif region:
            parent = get_object_or_404(Region, pk=region)
            level, crumbs = "district", [parent]
            groups = {row.pk: (row.name, []) for row in District.objects.filter(region=parent)}
            for row in localities.filter(ward__district__region=parent):
                groups[row.ward.district_id][1].append(row)
            pro_area = None
        else:
            level, crumbs = "region", []
            groups = {row.pk: (row.name, []) for row in Region.objects.all()}
            for row in localities:
                groups[row.ward.district.region_id][1].append(row)
            pro_area = None

        def professionals(key):
            counts = defaultdict(int)
            for pro in pros:
                region_ids = {item.pk for item in pro.regions.all()}
                district_ids = {item.pk for item in pro.districts.all()}
                if level == "region":
                    hit = key in region_ids or any(district_region.get(item) == key for item in district_ids)
                elif level == "district":
                    hit = key in district_ids or district_region.get(key) in region_ids
                else:
                    hit = pro_area[1] in district_ids or district_region.get(pro_area[1]) in region_ids
                if hit:
                    counts[pro.professional_type] += 1
            return counts

        rows = []
        for key, (name, members) in groups.items():
            ids = [row.pk for row in members]
            officials = set().union(*(officials_by_locality[item] for item in ids)) if ids else set()
            rows.append({
                "id": str(key), "name": name, "localities": len(ids),
                "covered": sum(1 for item in ids if officials_by_locality[item]),
                "officials": len(officials), "waiting": sum(waiting[item] for item in ids),
                "professionals": professionals(key),
            })
        rows.sort(key=lambda row: row["name"])
        # Distinct professionals covering the whole area shown, for the summary cards.
        totals = defaultdict(int)
        for pro in pros:
            region_ids = {item.pk for item in pro.regions.all()}
            district_ids = {item.pk for item in pro.districts.all()}
            if level == "region":
                hit = True
            elif level == "district":
                hit = parent.pk in region_ids or any(district_region.get(item) == parent.pk for item in district_ids)
            else:
                hit = pro_area[1] in district_ids or district_region.get(pro_area[1]) in region_ids
            if hit:
                totals[pro.professional_type] += 1
        return Response({"level": level, "crumbs": [{"id": str(item.pk), "name": item.name} for item in crumbs], "rows": rows, "professionals": totals})


class PublicRegistrationInput(serializers.Serializer):
    full_name = serializers.CharField(max_length=255)
    position = serializers.ChoiceField(choices=LocalOfficialProfile.Position.choices)
    national_id_number = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(max_length=128, write_only=True)
    photo = serializers.FileField()
    stamp_photo = serializers.FileField()


class PublicRegistrationView(generics.GenericAPIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = PublicRegistrationInput

    def get(self, request, token):
        invite = live_invite(token)
        return Response({"locality": _place(invite.locality), "phone": _mask(invite.phone), "expires_at": invite.expires_at, "replacement": invite.replaces_id is not None})

    def post(self, request, token):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        profile = register_official(token=token, request=request, **serializer.validated_data)
        return Response({"official_id": profile.official_id, "status": profile.status}, status=status.HTTP_201_CREATED)
