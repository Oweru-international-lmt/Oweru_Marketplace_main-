from django.urls import path
from . import management_views as views

urlpatterns = [
    path("", views.StaffAccountCreateView.as_view(), name="management-account-create"),
    path("<uuid:user_id>/", views.StaffAccountUpdateView.as_view(), name="management-account-update"),
    path("<uuid:user_id>/temporary-password/", views.StaffAccountPasswordResetView.as_view(), name="management-account-password"),
    path("<uuid:user_id>/deactivate/", views.StaffAccountActiveView.as_view(), name="management-account-deactivate"),
    path("<uuid:user_id>/reactivate/", views.StaffAccountReactivateView.as_view(), name="management-account-reactivate"),
    path("deletion-requests/", views.DeletionRequestListView.as_view(), name="management-deletion-requests"),
    path("deletion-requests/<uuid:request_id>/resolve/", views.DeletionRequestResolveView.as_view(),
         name="management-deletion-resolve"),
]
