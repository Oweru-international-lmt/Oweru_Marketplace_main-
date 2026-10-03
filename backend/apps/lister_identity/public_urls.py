from django.urls import path

from .views import PublicListerProfileView


urlpatterns = [
    path("<uuid:identity_id>/", PublicListerProfileView.as_view(), name="public-lister-profile"),
]
