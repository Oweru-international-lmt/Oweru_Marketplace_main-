from django.urls import path

from .views import (
    ManagementListerIdentityApproveView,
    ManagementListerIdentityDetailView,
    ManagementListerIdentityEvidenceView,
    ManagementListerIdentityListView,
    ManagementListerIdentityRejectView,
)


urlpatterns = [
    path("", ManagementListerIdentityListView.as_view(), name="management-lister-identity-list"),
    path("<uuid:pk>/", ManagementListerIdentityDetailView.as_view(), name="management-lister-identity-detail"),
    path("<uuid:pk>/evidence/<str:kind>/", ManagementListerIdentityEvidenceView.as_view(), name="management-lister-identity-evidence"),
    path("<uuid:pk>/approve/", ManagementListerIdentityApproveView.as_view(), name="management-lister-identity-approve"),
    path("<uuid:pk>/reject/", ManagementListerIdentityRejectView.as_view(), name="management-lister-identity-reject"),
]
