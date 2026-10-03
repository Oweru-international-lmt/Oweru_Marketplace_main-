from django.urls import path

from .views import AccountDeletionRequestView, CurrentUserProfileView


urlpatterns = [
    path("me/", CurrentUserProfileView.as_view(), name="user-profile"),
    path("me/deletion-request/", AccountDeletionRequestView.as_view(), name="account-deletion-request"),
]
