from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .managers import normalize_email_address
from .models import User


class UserPublicSerializer(serializers.ModelSerializer):
    # Effective access only, so clients can show the right screens. The API
    # still enforces every permission; these lists are not authorization.
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    email_verified = serializers.SerializerMethodField()
    phone_verified = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "phone",
            "full_name",
            "email",
            "language",
            "account_category",
            "roles",
            "permissions",
            "email_verified",
            "phone_verified",
            "must_change_password",
            "created_at",
        )
        read_only_fields = fields

    def get_roles(self, user):
        return sorted(user.effective_role_codes())

    def get_permissions(self, user):
        return sorted(user.effective_permission_codes())

    def get_email_verified(self, user):
        return user.email_verified_at is not None

    def get_phone_verified(self, user):
        return user.phone_verified_at is not None


def validate_unique_phone(value, exclude_pk=None):
    value = value.strip()
    if not value:
        raise serializers.ValidationError("Phone is required.")
    if User.objects.filter(phone=value).exclude(pk=exclude_pk).exists():
        raise serializers.ValidationError("An account with this phone already exists.")
    return value


def validate_unique_email(value):
    value = normalize_email_address(value)
    if User.objects.filter(email=value).exists():
        raise serializers.ValidationError("An account with this email already exists.")
    return value


def validate_full_name(value):
    value = value.strip()
    if not value:
        raise serializers.ValidationError("Full name is required.")
    return value


class ProfileUpdateSerializer(serializers.Serializer):
    """Fields a person may change on their own profile (ACC-08). Email is the
    sign-in identifier and is not changed here."""

    full_name = serializers.CharField(max_length=255, required=False)
    phone = serializers.CharField(max_length=30, required=False)
    language = serializers.ChoiceField(choices=User.Language.choices, required=False)

    def validate_full_name(self, value):
        return validate_full_name(value)

    def validate_phone(self, value):
        target = self.context.get("target")
        return validate_unique_phone(value, exclude_pk=target.pk if target else None)


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False, write_only=True)
    new_password = serializers.CharField(trim_whitespace=False, write_only=True)


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class LinkConfirmationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    token = serializers.CharField()


class ConfirmationDecisionSerializer(serializers.Serializer):
    token = serializers.CharField()
    decision = serializers.ChoiceField(choices=["confirmed", "declined"])


class DeletionRequestCreateSerializer(serializers.Serializer):
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True)


class DeletionRequestSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    status = serializers.CharField()
    reason = serializers.CharField()
    requested_at = serializers.DateTimeField()
    resolved_at = serializers.DateTimeField(allow_null=True)
    resolution_note = serializers.CharField()


class RegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, trim_whitespace=False, style={"input_type": "password"})

    class Meta:
        model = User
        fields = ("email", "phone", "full_name", "password", "language")
        # The model's unique validator would compare the raw value; validate_email
        # checks uniqueness after lowercasing instead.
        extra_kwargs = {"email": {"validators": []}}

    def validate_email(self, value):
        return validate_unique_email(value)

    def validate_phone(self, value):
        return validate_unique_phone(value)

    def validate_full_name(self, value):
        return validate_full_name(value)

    def validate_password(self, value):
        try:
            validate_password(value)
        except DjangoValidationError as exc:
            raise serializers.ValidationError(list(exc.messages)) from exc
        return value

    def create(self, validated_data):
        from authorization.services import register_public_user

        return register_public_user(request=self.context.get("request"), **validated_data)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(trim_whitespace=False, write_only=True)


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
