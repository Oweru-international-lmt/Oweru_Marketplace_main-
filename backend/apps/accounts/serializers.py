from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .managers import normalize_email_address
from .models import AccountDeletionRequest, User


class UserPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "phone", "full_name", "email", "preferred_language", "is_email_verified", "created_at")
        read_only_fields = fields


class UserPrivateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "phone",
            "full_name",
            "preferred_language",
            "is_email_verified",
            "created_at",
            "date_joined",
        )
        read_only_fields = ("id", "email", "phone", "is_email_verified", "created_at", "date_joined")

    def validate_full_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Full name is required.")
        return value


class AccountDeletionRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccountDeletionRequest
        fields = ("id", "status", "reason", "requested_at")
        read_only_fields = ("id", "status", "requested_at")

    def validate_reason(self, value):
        return value.strip()


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "phone", "full_name", "password", "preferred_language")
        # The model's unique validator would compare the raw value; validate_email
        # checks uniqueness after lowercasing instead.
        extra_kwargs = {"email": {"validators": []}}

    def validate_email(self, value):
        value = normalize_email_address(value)
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("An account with this email already exists.")
        return value

    def validate_phone(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Phone is required.")
        if User.objects.filter(phone=value).exists():
            raise serializers.ValidationError("An account with this phone already exists.")
        return value

    def validate_full_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Full name is required.")
        return value

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        from apps.roles.services import register_public_user

        return register_public_user(request=self.context.get("request"), **validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(trim_whitespace=False, write_only=True)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password_confirm = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_new_password(self, value):
        if not value or not value.strip():
            raise serializers.ValidationError("New password is required.")
        return value

    def validate(self, attrs):
        user = self.context["request"].user
        current_password = attrs["current_password"]
        new_password = attrs["new_password"]
        if not user.check_password(current_password):
            raise serializers.ValidationError({"current_password": "Current password is incorrect."})
        if new_password != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "New passwords do not match."})
        if current_password == new_password:
            raise serializers.ValidationError({"new_password": "New password must be different from the current password."})
        try:
            validate_password(new_password, user=user)
        except DjangoValidationError as exc:
            raise serializers.ValidationError({"new_password": list(exc.messages)}) from exc
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField()
    token = serializers.CharField()
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)

    def validate_new_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value


class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField(trim_whitespace=False)
