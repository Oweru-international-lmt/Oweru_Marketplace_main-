from django.urls import path

from apps.verification.views import (
    LocalOfficialFieldVerificationApproveView,
    LocalOfficialFieldVerificationRejectView,
    LocalOfficialFieldVerificationReviewDetailView,
    LocalOfficialFieldVerificationReviewQueueView,
)

from .views import LocalOfficialSelfJurisdictionView, LocalOfficialSelfProfileView


urlpatterns = [
    path("me/", LocalOfficialSelfProfileView.as_view(), name="local-official-self"),
    path(
        "me/jurisdictions/",
        LocalOfficialSelfJurisdictionView.as_view(),
        name="local-official-self-jurisdictions",
    ),
    path(
        "verifications/field/",
        LocalOfficialFieldVerificationReviewQueueView.as_view(),
        name="local-official-field-verification-queue",
    ),
    path(
        "verifications/field/<uuid:verification_id>/",
        LocalOfficialFieldVerificationReviewDetailView.as_view(),
        name="local-official-field-verification-detail",
    ),
    path(
        "verifications/field/<uuid:verification_id>/approve/",
        LocalOfficialFieldVerificationApproveView.as_view(),
        name="local-official-field-verification-approve",
    ),
    path(
        "verifications/field/<uuid:verification_id>/reject/",
        LocalOfficialFieldVerificationRejectView.as_view(),
        name="local-official-field-verification-reject",
    ),
]
