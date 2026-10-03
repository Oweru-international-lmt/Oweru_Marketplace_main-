"""Management account administration (ACC-06 staff accounts, ACC-08 deletion requests).

Same access model as the authorization APIs: JWT, an active Management role and
the named permission. Responses carry no email or phone, except the temporary
password that is shown once so it can be passed to the new staff member.
"""
from rest_framework import serializers, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from authorization.permissions import HasMarketplacePermission, IsManagement
from authorization.serializers import AccountLookupSerializer
from authorization.views import ManagementAuthorizationView
from . import account_services
from .models import AccountDeletionRequest, User
from .serializers import ProfileUpdateSerializer, validate_full_name, validate_unique_email, validate_unique_phone


class StaffAccountCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30)
    full_name = serializers.CharField(max_length=255)
    language = serializers.ChoiceField(choices=User.Language.choices, default=User.Language.SWAHILI)

    def validate_email(self, value):
        return validate_unique_email(value)

    def validate_phone(self, value):
        return validate_unique_phone(value)

    def validate_full_name(self, value):
        return validate_full_name(value)


class ReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=1000)


class DeletionResolveSerializer(serializers.Serializer):
    decision = serializers.ChoiceField(choices=["completed", "declined"])
    note = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")


class ManagementDeletionRequestSerializer(serializers.ModelSerializer):
    account = AccountLookupSerializer(source="user")

    class Meta:
        model = AccountDeletionRequest
        fields = ("id", "account", "reason", "status", "requested_at", "resolved_at", "resolution_note")


class ManagementAccountView(ManagementAuthorizationView):
    permission_classes = [IsAuthenticated, IsManagement, HasMarketplacePermission]
    required_marketplace_permission = "account.manage"


class StaffAccountCreateView(ManagementAccountView):
    serializer_class = StaffAccountCreateSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user, password = account_services.create_staff_account(actor=request.user, request=request, **serializer.validated_data)
        return Response(
            {"account": AccountLookupSerializer(user).data, "temporary_password": password},
            status=status.HTTP_201_CREATED,
        )


class StaffAccountUpdateView(ManagementAccountView):
    serializer_class = ProfileUpdateSerializer

    def patch(self, request, user_id, *args, **kwargs):
        target = User.objects.filter(pk=user_id).first()
        serializer = self.get_serializer(data=request.data, context={**self.get_serializer_context(), "target": target})
        serializer.is_valid(raise_exception=True)
        user = account_services.update_staff_account(actor=request.user, user_id=user_id, changes=serializer.validated_data,
                                                     request=request)
        return Response(AccountLookupSerializer(user).data)


class StaffAccountPasswordResetView(ManagementAccountView):
    def post(self, request, user_id, *args, **kwargs):
        user, password = account_services.reset_staff_password(actor=request.user, user_id=user_id, request=request)
        return Response({"account": AccountLookupSerializer(user).data, "temporary_password": password})


class StaffAccountActiveView(ManagementAccountView):
    serializer_class = ReasonSerializer
    required_marketplace_permission = "account.suspend"
    active = False

    def post(self, request, user_id, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = account_services.set_staff_account_active(actor=request.user, user_id=user_id, active=self.active,
                                                         reason=serializer.validated_data["reason"], request=request)
        return Response(AccountLookupSerializer(user).data)


class StaffAccountReactivateView(StaffAccountActiveView):
    active = True


class DeletionRequestListView(ManagementAccountView):
    serializer_class = ManagementDeletionRequestSerializer

    def get(self, request, *args, **kwargs):
        wanted = request.query_params.get("status", AccountDeletionRequest.Status.PENDING)
        if wanted not in AccountDeletionRequest.Status.values:
            return Response({"status": ["Unknown status."]}, status=status.HTTP_400_BAD_REQUEST)
        queryset = AccountDeletionRequest.objects.filter(status=wanted).select_related("user")
        return Response(self.get_serializer(queryset, many=True).data)


class DeletionRequestResolveView(ManagementAccountView):
    serializer_class = DeletionResolveSerializer

    def post(self, request, request_id, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deletion = account_services.resolve_deletion(deletion_id=request_id, actor=request.user, request=request,
                                                     **serializer.validated_data)
        return Response(ManagementDeletionRequestSerializer(deletion).data)
