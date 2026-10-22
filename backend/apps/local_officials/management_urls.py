from django.urls import path
from .full_check_api import LocalityCoverageView, RevokeLocalityView
from .partner_api import CoverageView, InviteCancelView, InviteCollectionView, InviteResendView, OfficialApproveView, OfficialDeactivateView, OfficialListView, OfficialPhotoView

from .views import (
    ManagementLocalOfficialJurisdictionCollectionView,
    ManagementLocalOfficialJurisdictionRevokeView,
    ManagementLocalOfficialProfileCollectionView,
    ManagementLocalOfficialProfileDetailView,
)


urlpatterns = [
    path("overview/", OfficialListView.as_view()),
    path("coverage/", CoverageView.as_view()),
    path("invites/", InviteCollectionView.as_view()),
    path("invites/<uuid:invite_id>/resend/", InviteResendView.as_view()),
    path("invites/<uuid:invite_id>/cancel/", InviteCancelView.as_view()),
    path("<str:official_id>/approve/", OfficialApproveView.as_view()),
    path("<str:official_id>/deactivate/", OfficialDeactivateView.as_view()),
    path("<str:official_id>/photos/<str:kind>/", OfficialPhotoView.as_view()),
    path("<str:official_id>/localities/", LocalityCoverageView.as_view()),
    path("<str:official_id>/localities/<uuid:coverage_id>/revoke/", RevokeLocalityView.as_view()),
    path("", ManagementLocalOfficialProfileCollectionView.as_view(), name="management-local-official-list"),
    path("<str:official_id>/", ManagementLocalOfficialProfileDetailView.as_view(), name="management-local-official-detail"),
    path(
        "<str:official_id>/jurisdictions/",
        ManagementLocalOfficialJurisdictionCollectionView.as_view(),
        name="management-local-official-jurisdiction-list",
    ),
    path(
        "<str:official_id>/jurisdictions/<str:assignment_id>/revoke/",
        ManagementLocalOfficialJurisdictionRevokeView.as_view(),
        name="management-local-official-jurisdiction-revoke",
    ),
]
