from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.listings.urls import management_urlpatterns as listing_management_urlpatterns
from apps.properties.urls import management_duplicate_urlpatterns as property_duplicate_management_urlpatterns
from apps.payments.urls import deal_urlpatterns, payout_urlpatterns, management_urlpatterns as finance_management_urlpatterns

urlpatterns = [
    path("", include("apps.common.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("users/", include("apps.accounts.profile_urls")),
    path("localities/", include("apps.localities.urls")),
    path("properties/", include("apps.properties.urls")),
    path("listings/", include("apps.listings.urls")),
    path("media/", include("apps.media.urls")),
    path("leads/", include("apps.leads.urls")),
    path("deals/", include((deal_urlpatterns, "deals"))),
    path("commissions/", include("apps.commissions.urls")),
    path("payments/", include("apps.payments.urls")),
    path("payouts/", include((payout_urlpatterns, "payouts"))),
    path("management/finance/", include((finance_management_urlpatterns, "finance-management"))),
    path("lister-identity/", include("apps.lister_identity.urls")),
    path("public/listings/", include("apps.listings.public_urls")),
    path("listers/", include("apps.lister_identity.public_urls")),
    path("management/lister-identities/", include("apps.lister_identity.management_urls")),
    path("management/listings/", include((listing_management_urlpatterns, "management-listings"))),
    path(
        "management/property-duplicates/",
        include((property_duplicate_management_urlpatterns, "management-property-duplicates")),
    ),
    path("management/authorization/", include("apps.roles.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="api-redoc"),
]
