import logging

from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework.views import APIView

from .auth_services import authenticate_phone_password, issue_jwt_pair
from .models import User
from .reset_services import reset_password, send_reset_link
from .serializers import LoginSerializer, PasswordResetConfirmSerializer, PasswordResetRequestSerializer, RegistrationSerializer, UserPublicSerializer

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
        return Response(UserPublicSerializer(user).data, status=status.HTTP_201_CREATED)


class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate_phone_password(**serializer.validated_data)
        if user is None:
            return Response({"detail": "Invalid phone or password."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({**issue_jwt_pair(user), "user": UserPublicSerializer(user).data})


class CurrentUserView(generics.RetrieveAPIView):
    serializer_class = UserPublicSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request, *args, **kwargs):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = User.objects.filter(phone=serializer.validated_data["phone"], is_active=True).first()
        if user and user.email:
            try:
                send_reset_link(user)
            except Exception:
                logger.exception("Password reset email delivery failed")
        return Response({
            "detail": "If the account has an email address, password reset instructions have been sent. Accounts without email should contact Oweru support through WhatsApp."
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
