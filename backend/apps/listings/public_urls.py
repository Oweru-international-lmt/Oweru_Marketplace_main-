from django.urls import path

from .public_views import PublicListingCollectionView, PublicListingDetailView


urlpatterns = [
    path("", PublicListingCollectionView.as_view(), name="public-listing-list"),
    path("<str:listing_id>/", PublicListingDetailView.as_view(), name="public-listing-detail"),
]
