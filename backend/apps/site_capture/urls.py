from django.urls import path

from .views import (
    PropertySiteCaptureCollectionView,
    SiteCaptureDetailView,
    SiteCaptureMediaCollectionView,
    SiteCaptureMediaDetailView,
    SiteCapturePromoteView,
    SiteCaptureSubmitView,
)


property_urlpatterns = [
    path("<str:property_id>/site-captures/", PropertySiteCaptureCollectionView.as_view(), name="property-site-capture-list"),
]

urlpatterns = [
    path("<str:capture_id>/", SiteCaptureDetailView.as_view(), name="site-capture-detail"),
    path("<str:capture_id>/submit/", SiteCaptureSubmitView.as_view(), name="site-capture-submit"),
    path("<str:capture_id>/promote/", SiteCapturePromoteView.as_view(), name="site-capture-promote"),
    path("<str:capture_id>/media/", SiteCaptureMediaCollectionView.as_view(), name="site-capture-media-upload"),
    path("<str:capture_id>/media/<str:media_id>/", SiteCaptureMediaDetailView.as_view(), name="site-capture-media-remove"),
]
