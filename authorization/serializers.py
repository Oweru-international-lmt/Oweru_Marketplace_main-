from rest_framework import serializers

from .models import Permission, Role, RoleCode, UserRole
from . import services


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ("code", "name", "is_active")


class PermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Permission
        fields = ("code", "name", "description")


class UserRoleSerializer(serializers.ModelSerializer):
    role_code = serializers.CharField(source="role.code")

    class Meta:
        model = UserRole
        fields = ("role_code", "is_active")


class RoleMutationSerializer(serializers.Serializer):
    role_code = serializers.ChoiceField(choices=RoleCode.choices)

    def create(self, validated_data):
        request = self.context["request"]
        kwargs = dict(user=self.context["target"], request=request, **validated_data)
        if self.context["operation"] == "assign":
            return services.assign_role(assigned_by=request.user, **kwargs)
        return services.revoke_role(revoked_by=request.user, **kwargs)


class OutboxGrantSerializer(serializers.Serializer):
    enabled = serializers.BooleanField()

    def create(self, validated_data):
        request = self.context["request"]
        operation = services.grant_permission if validated_data["enabled"] else services.revoke_permission
        operation(role_code=self.context["role_code"], permission_code="outbox.send", actor=request.user, request=request)
        return validated_data
