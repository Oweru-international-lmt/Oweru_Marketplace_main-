from django.urls import path

from .views import (
    DocumentVerificationApproveView,
    DocumentVerificationRejectView,
    DocumentVerificationReviewDetailView,
    DocumentVerificationReviewQueueView,
    DocumentVerificationRevokeView,
    FieldVerificationApproveView,
    FieldVerificationRejectView,
    FieldVerificationReviewDetailView,
    FieldVerificationReviewQueueView,
    FieldVerificationRevokeView,
    PropertyDocumentVerificationSubmissionView,
    PropertyFieldVerificationSubmissionView,
    PropertyVerificationStatusView,
)


urlpatterns = [
    path(
        "properties/<str:property_id>/documents/",
        PropertyDocumentVerificationSubmissionView.as_view(),
        name="property-document-verification-submit",
    ),
    path(
        "properties/<str:property_id>/field/",
        PropertyFieldVerificationSubmissionView.as_view(),
        name="property-field-verification-submit",
    ),
    path(
        "properties/<str:property_id>/",
        PropertyVerificationStatusView.as_view(),
        name="property-verification-status",
    ),
]

management_urlpatterns = [
    path("documents/", DocumentVerificationReviewQueueView.as_view(), name="document-verification-review-list"),
    path(
        "documents/<uuid:verification_id>/",
        DocumentVerificationReviewDetailView.as_view(),
        name="document-verification-review-detail",
    ),
    path(
        "documents/<uuid:verification_id>/approve/",
        DocumentVerificationApproveView.as_view(),
        name="document-verification-approve",
    ),
    path(
        "documents/<uuid:verification_id>/reject/",
        DocumentVerificationRejectView.as_view(),
        name="document-verification-reject",
    ),
    path(
        "documents/<uuid:verification_id>/revoke/",
        DocumentVerificationRevokeView.as_view(),
        name="document-verification-revoke",
    ),
    path("field/", FieldVerificationReviewQueueView.as_view(), name="field-verification-review-list"),
    path(
        "field/<uuid:verification_id>/",
        FieldVerificationReviewDetailView.as_view(),
        name="field-verification-review-detail",
    ),
    path(
        "field/<uuid:verification_id>/approve/",
        FieldVerificationApproveView.as_view(),
        name="field-verification-approve",
    ),
    path(
        "field/<uuid:verification_id>/reject/",
        FieldVerificationRejectView.as_view(),
        name="field-verification-reject",
    ),
    path(
        "field/<uuid:verification_id>/revoke/",
        FieldVerificationRevokeView.as_view(),
        name="field-verification-revoke",
    ),
]
