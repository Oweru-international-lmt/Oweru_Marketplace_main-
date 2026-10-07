from django.urls import path

from .views import (
    ManagementLocalOfficialJurisdictionCollectionView,
    ManagementLocalOfficialJurisdictionRevokeView,
    ManagementLocalOfficialProfileCollectionView,
    ManagementLocalOfficialProfileDetailView,
)


urlpatterns = [
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
