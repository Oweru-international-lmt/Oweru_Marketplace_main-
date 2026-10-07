from django.urls import path

from .views import (
    ManagementPossibleDuplicateCollectionView,
    ManagementPossibleDuplicateConfirmView,
    ManagementPossibleDuplicateDetailView,
    ManagementPossibleDuplicateDismissView,
    PropertyRecordCollectionView,
    PropertyRecordDetailView,
)
from apps.site_capture.urls import property_urlpatterns as site_capture_property_urlpatterns


urlpatterns = [
    *site_capture_property_urlpatterns,
    path("", PropertyRecordCollectionView.as_view(), name="property-record-list"),
    path("<str:property_id>/", PropertyRecordDetailView.as_view(), name="property-record-detail"),
]

management_duplicate_urlpatterns = [
    path("", ManagementPossibleDuplicateCollectionView.as_view(), name="management-property-duplicate-list"),
    path("<uuid:duplicate_id>/", ManagementPossibleDuplicateDetailView.as_view(), name="management-property-duplicate-detail"),
    path(
        "<uuid:duplicate_id>/confirm/",
        ManagementPossibleDuplicateConfirmView.as_view(),
        name="management-property-duplicate-confirm",
    ),
    path(
        "<uuid:duplicate_id>/dismiss/",
        ManagementPossibleDuplicateDismissView.as_view(),
        name="management-property-duplicate-dismiss",
    ),
]
