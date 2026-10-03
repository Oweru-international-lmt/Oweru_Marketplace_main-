from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication

from accounts.managers import normalize_email_address
from accounts.models import User
from .models import Permission, Role, UserRole
from .permissions import HasMarketplacePermission, IsManagement
from .serializers import (
    AccountLookupSerializer,
    OutboxGrantSerializer,
    PermissionSerializer,
    RoleMutationSerializer,
    RoleSerializer,
    UserRoleSerializer,
)


class ManagementAuthorizationView(generics.GenericAPIView):
    authentication_classes = [JWTAuthentication]
    permission_classes = [IsAuthenticated, IsManagement, HasMarketplacePermission]
    required_marketplace_permission = "authorization.view"


class RoleListView(ManagementAuthorizationView, generics.ListAPIView):
    serializer_class = RoleSerializer
    queryset = Role.objects.all()


class PermissionListView(ManagementAuthorizationView, generics.ListAPIView):
    serializer_class = PermissionSerializer
    queryset = Permission.objects.all()


class RolePermissionListView(ManagementAuthorizationView, generics.ListAPIView):
    serializer_class = PermissionSerializer

    def get_queryset(self):
        role = get_object_or_404(Role, code=self.kwargs["role_code"])
        return Permission.objects.filter(role_permissions__role=role)


class AccountLookupView(ManagementAuthorizationView, generics.ListAPIView):
    """Find one account by exact email so Management can manage its roles.

    Exact match only: there is no partial search or listing, so the user
    table cannot be browsed or enumerated through this endpoint.
    """

    serializer_class = AccountLookupSerializer

    def get_queryset(self):
        email = normalize_email_address(self.request.query_params.get("email", ""))
        if not email:
            raise ValidationError({"email": "An email address is required."})
        return User.objects.filter(email=email)


class UserRoleListView(ManagementAuthorizationView, generics.ListAPIView):
    serializer_class = UserRoleSerializer

    def get_queryset(self):
        user = get_object_or_404(User, pk=self.kwargs["user_id"])
        return UserRole.objects.filter(user=user).select_related("role").order_by("role__code")


class AssignRoleView(ManagementAuthorizationView):
    serializer_class = RoleMutationSerializer
    required_marketplace_permission = "authorization.assign_role"
    operation = "assign"

    def post(self, request, *args, **kwargs):
        target = get_object_or_404(User, pk=kwargs["user_id"])
        context = {**self.get_serializer_context(), "target": target, "operation": self.operation}
        serializer = self.get_serializer(data=request.data, context=context)
        serializer.is_valid(raise_exception=True)
        result = serializer.save()
        if self.operation == "revoke":
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(UserRoleSerializer(result).data)


class RevokeRoleView(AssignRoleView):
    required_marketplace_permission = "authorization.revoke_role"
    operation = "revoke"


class OutboxGrantView(ManagementAuthorizationView):
    serializer_class = OutboxGrantSerializer
    required_marketplace_permission = "authorization.manage_outbox"

    def put(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={**self.get_serializer_context(), "role_code": kwargs["role_code"]})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
