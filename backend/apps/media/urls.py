from django.urls import path

from .views import ImageMediaUploadView, MediaAccessView


urlpatterns = [
    path("images/", ImageMediaUploadView.as_view(), name="media-image-upload"),
    path("<str:media_id>/access/", MediaAccessView.as_view(), name="media-access"),
]
