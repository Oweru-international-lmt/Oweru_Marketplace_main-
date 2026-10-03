import logging

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from .auth_services import authenticate_email_password, blacklist_refresh_token_for_user, change_user_password, issue_jwt_pair
from .deletion_services import request_account_deletion
from .email_verification import send_email_verification_safely, verify_email_token
from .managers import normalize_email_address
from .models import User
from .reset_services import reset_password, send_reset_link
from .serializers import (
    AccountDeletionRequestSerializer,
    EmailVerificationSerializer,
    LoginSerializer,
    LogoutSerializer,
    PasswordChangeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    RegistrationSerializer,
    UserPrivateProfileSerializer,
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
        send_email_verification_safely(user)
        return Response(UserPublicSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_email_password(**serializer.validated_data, request=request)
        if user is None:
            return Response({"detail": "Invalid email or password."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({**issue_jwt_pair(user), "user": UserPublicSerializer(user).data})


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not blacklist_refresh_token_for_user(request.user, serializer.validated_data["refresh"], request=request):
            return Response({"detail": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Logged out successfully."})


class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserPrivateProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class CurrentUserProfileView(generics.RetrieveUpdateAPIView):
    http_method_names = ["get", "patch", "head", "options"]
    serializer_class = UserPrivateProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class AccountDeletionRequestView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = AccountDeletionRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deletion_request = request_account_deletion(
            user=request.user,
            reason=serializer.validated_data.get("reason", ""),
            request=request,
        )
        return Response(AccountDeletionRequestSerializer(deletion_request).data, status=status.HTTP_201_CREATED)


class PasswordChangeView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = PasswordChangeSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        change_user_password(request.user, serializer.validated_data["new_password"], request=request)
        return Response({"detail": "Credentials updated successfully."})


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
        if not reset_password(**serializer.validated_data, request=request):
            return Response({"detail": "The reset link is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Password reset successfully."})


class EmailVerificationView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not verify_email_token(serializer.validated_data["token"], request=request):
            return Response({"detail": "The verification link is invalid or expired."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Email verified successfully."})


class EmailVerificationResendView(APIView):
    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        if not request.user.is_email_verified:
            send_email_verification_safely(request.user)
        return Response({"detail": "If verification is needed, a verification email has been sent."})
