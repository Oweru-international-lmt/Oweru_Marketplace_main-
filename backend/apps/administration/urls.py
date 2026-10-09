from django.urls import path
from .api import DashboardView, SettingsView, AccountView, ListingView, AuditView

urlpatterns = [path("dashboard/", DashboardView.as_view()), path("settings/", SettingsView.as_view()), path("settings/<str:setting_key>/", SettingsView.as_view()), path("accounts/", AccountView.as_view()), path("accounts/<uuid:user_id>/", AccountView.as_view()), path("listing-actions/<str:listing_id>/", ListingView.as_view()), path("audit/", AuditView.as_view())]
