from django.urls import path
from .full_check_api import LocalityCoverageView, RevokeLocalityView

from .views import (
    ManagementLocalOfficialJurisdictionCollectionView,
    ManagementLocalOfficialJurisdictionRevokeView,
    ManagementLocalOfficialProfileCollectionView,
    ManagementLocalOfficialProfileDetailView,
)


urlpatterns = [
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
