from django.urls import path

from .views import (
    ListingActivateView,
    ListingCollectionView,
    ListingDetailView,
    ListingPhotoCollectionView,
    ListingPhotoDetailView,
    ListingPhotoReorderView,
    ListingWithdrawView,
    ManagementListingRestoreView,
    ManagementListingSuspendView,
)


urlpatterns = [
    path("", ListingCollectionView.as_view(), name="listing-list"),
    path("<str:listing_id>/", ListingDetailView.as_view(), name="listing-detail"),
    path("<str:listing_id>/activate/", ListingActivateView.as_view(), name="listing-activate"),
    path("<str:listing_id>/withdraw/", ListingWithdrawView.as_view(), name="listing-withdraw"),
    path("<str:listing_id>/photos/", ListingPhotoCollectionView.as_view(), name="listing-photo-list"),
    path("<str:listing_id>/photos/reorder/", ListingPhotoReorderView.as_view(), name="listing-photo-reorder"),
    path("<str:listing_id>/photos/<uuid:photo_id>/", ListingPhotoDetailView.as_view(), name="listing-photo-detail"),
]

management_urlpatterns = [
    path("<str:listing_id>/suspend/", ManagementListingSuspendView.as_view(), name="management-listing-suspend"),
    path("<str:listing_id>/restore/", ManagementListingRestoreView.as_view(), name="management-listing-restore"),
]
