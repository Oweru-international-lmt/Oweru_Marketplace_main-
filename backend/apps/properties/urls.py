from django.urls import path

from .views import PropertyRecordCollectionView, PropertyRecordDetailView


urlpatterns = [
    path("", PropertyRecordCollectionView.as_view(), name="property-record-list"),
    path("<str:property_id>/", PropertyRecordDetailView.as_view(), name="property-record-detail"),
]
