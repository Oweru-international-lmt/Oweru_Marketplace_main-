from django.urls import path
from .views import (
    ConfirmationLinkView,
    CurrentUserView,
    DeletionRequestView,
    EmailConfirmView,
    EmailResendView,
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
    path("me/", CurrentUserView.as_view(), name="current-user"),
    path("me/deletion-request/", DeletionRequestView.as_view(), name="deletion-request"),
    path("password/change/", PasswordChangeView.as_view(), name="password-change"),
    path("password/reset/", PasswordResetRequestView.as_view(), name="password-reset-request"),
    path("password/reset/confirm/", PasswordResetConfirmView.as_view(), name="password-reset-confirm"),
    path("email/confirm/", EmailConfirmView.as_view(), name="email-confirm"),
    path("email/resend/", EmailResendView.as_view(), name="email-resend"),
    path("confirmations/<uuid:confirmation_id>/", ConfirmationLinkView.as_view(), name="confirmation-link"),
]
