from django.urls import path
from .views import (
    CurrentUserView,
    EmailVerificationResendView,
    EmailVerificationView,
    LoginView,
    LogoutView,
    PasswordChangeView,
    PasswordResetConfirmView,
    PasswordResetRequestView,
    RegistrationView,
)

urlpatterns = [
    path("register/", RegistrationView.as_view(), name="register"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("email/verify/", EmailVerificationView.as_view(), name="email-verify"),
    path("email/resend/", EmailVerificationResendView.as_view(), name="email-resend"),
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password/reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
]
