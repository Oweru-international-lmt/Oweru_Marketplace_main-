from django.urls import path

from .views import (
    DistrictDetailView,
    DistrictListView,
    LocalityApproveView,
    LocalityCollectionView,
    LocalityDetailView,
    RegionDetailView,
    RegionListView,
    WardDetailView,
    WardListView,
)


urlpatterns = [
    path("regions/", RegionListView.as_view(), name="region-list"),
    path("regions/<uuid:pk>/", RegionDetailView.as_view(), name="region-detail"),
    path("districts/", DistrictListView.as_view(), name="district-list"),
    path("districts/<uuid:pk>/", DistrictDetailView.as_view(), name="district-detail"),
    path("wards/", WardListView.as_view(), name="ward-list"),
    path("wards/<uuid:pk>/", WardDetailView.as_view(), name="ward-detail"),
    path("", LocalityCollectionView.as_view(), name="locality-list"),
    path("<uuid:pk>/approve/", LocalityApproveView.as_view(), name="locality-approve"),
    path("<uuid:pk>/", LocalityDetailView.as_view(), name="locality-detail"),
]
