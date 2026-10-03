import logging

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from . import account_services
from .auth_services import authenticate_email_password, issue_jwt_pair
from .confirmations import link_state
from .managers import normalize_email_address
from .models import SensitiveConfirmation, User
from .reset_services import reset_password, send_reset_link
from .serializers import (
    ConfirmationDecisionSerializer,
    DeletionRequestCreateSerializer,
    DeletionRequestSerializer,
    LinkConfirmationSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    ProfileUpdateSerializer,
    RegistrationSerializer,
    UserPublicSerializer,
)

logger = logging.getLogger(__name__)


class RegistrationView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegistrationSerializer
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "auth_register"

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        account_services.send_email_confirmation_safely(user)  # ACC-05
        return Response(UserPublicSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_email_password(**serializer.validated_data)
        if user is None:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({**issue_jwt_pair(user), "user": UserPublicSerializer(user).data})


class LogoutView(APIView):
    """Revoke the refresh token so the session cannot be renewed. Works with an
    expired access token, and is idempotent for unknown or invalid tokens."""

    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request, *args, **kwargs):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            RefreshToken(serializer.validated_data["refresh"]).blacklist()
        except TokenError:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class CurrentUserView(generics.GenericAPIView):
    """GET: own profile. PATCH: edit own name, phone or language (ACC-08)."""

    serializer_class = UserPublicSerializer
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        return Response(UserPublicSerializer(request.user).data)

    def patch(self, request, *args, **kwargs):
        if not request.user.has_marketplace_permission("account.update"):
            raise PermissionDenied("You do not have permission to edit this profile.")
        serializer = ProfileUpdateSerializer(data=request.data, context={"target": request.user})
        serializer.is_valid(raise_exception=True)
        user = account_services.update_profile(user=request.user, changes=serializer.validated_data, request=request)
        return Response(UserPublicSerializer(user).data)


class PasswordChangeView(APIView):
    """Change own password; also clears a temporary password (ACC-06). Returns a
    fresh token pair because all earlier sessions are ended."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = account_services.change_password(user=request.user, request=request, **serializer.validated_data)
        return Response({**issue_jwt_pair(user), "user": UserPublicSerializer(user).data})


class EmailConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "confirmation"

    def post(self, request, *args, **kwargs):
        serializer = LinkConfirmationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = account_services.confirm_email(
            confirmation_id=serializer.validated_data["id"], raw_token=serializer.validated_data["token"], request=request
        )
        if result != "confirmed":
            return Response({"detail": "The confirmation link is invalid or expired.", "state": result},
                            status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Email confirmed.", "state": result})


class EmailResendView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "email_resend"

    def post(self, request, *args, **kwargs):
        if request.user.email_verified_at:
            return Response({"detail": "Your email is already confirmed."}, status=status.HTTP_400_BAD_REQUEST)
        account_services.send_email_confirmation(request.user)
        return Response({"detail": "Confirmation email sent."})


def _mask_phone(phone):
    return f"{phone[:4]}{'•' * max(len(phone) - 7, 0)}{phone[-3:]}" if len(phone) > 7 else phone


class ConfirmationLinkView(APIView):
    """SRD 20.3 WhatsApp confirmation page. GET shows what is being confirmed;
    POST stores Confirm or Decline once. No sign-in needed: the token is the proof."""

    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "confirmation"

    def get(self, request, confirmation_id, *args, **kwargs):
        confirmation = SensitiveConfirmation.objects.filter(pk=confirmation_id).select_related("user").first()
        state = link_state(confirmation, request.query_params.get("token", ""), account_services.LINK_PURPOSES)
        if state == "invalid":
            return Response({"state": state}, status=status.HTTP_404_NOT_FOUND)
        return Response({
            "state": state,
            "purpose": confirmation.purpose,
            "recipient": _mask_phone(confirmation.recipient),
            "full_name": confirmation.user.full_name,
            "expires_at": confirmation.expires_at,
            "decision": confirmation.decision,
        })

    def post(self, request, confirmation_id, *args, **kwargs):
        serializer = ConfirmationDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = account_services.decide_confirmation_link(
            confirmation_id=confirmation_id, raw_token=serializer.validated_data["token"],
            decision=serializer.validated_data["decision"], request=request,
        )
        if result not in ("confirmed", "declined"):
            code = status.HTTP_404_NOT_FOUND if result == "invalid" else status.HTTP_400_BAD_REQUEST
            return Response({"detail": "This confirmation link can no longer be used.", "state": result}, status=code)
        return Response({"state": result})


class DeletionRequestView(APIView):
    """ACC-08: request, view or cancel deletion of one's own account."""

    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        latest = request.user.deletion_requests.first()
        return Response({"request": DeletionRequestSerializer(latest).data if latest else None})

    def post(self, request, *args, **kwargs):
        if not request.user.has_marketplace_permission("account.request_deletion"):
            raise PermissionDenied("You do not have permission to request deletion.")
        serializer = DeletionRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deletion = account_services.request_deletion(user=request.user, reason=serializer.validated_data.get("reason", ""),
                                                     request=request)
        return Response({"request": DeletionRequestSerializer(deletion).data}, status=status.HTTP_201_CREATED)

    def delete(self, request, *args, **kwargs):
        if account_services.cancel_deletion(user=request.user, request=request) is None:
            return Response({"detail": "There is no pending deletion request."}, status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = normalize_email_address(serializer.validated_data["email"])
        user = User.objects.filter(email=email, is_active=True).first()
        if user:
            try:
                send_reset_link(user)
            except Exception:
                logger.exception("Password reset email delivery failed")
        return Response({
            "detail": "If an account exists for this email address, password reset instructions have been sent."
        })


class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not reset_password(**serializer.validated_data):
            return Response({"detail": "The reset link is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Password reset successfully."})
