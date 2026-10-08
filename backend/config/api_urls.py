from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

from apps.listings.urls import management_urlpatterns as listing_management_urlpatterns
from apps.properties.urls import management_duplicate_urlpatterns as property_duplicate_management_urlpatterns
from apps.payments.urls import deal_urlpatterns, payout_urlpatterns, management_urlpatterns as finance_management_urlpatterns
from apps.verification.urls import management_urlpatterns as verification_management_urlpatterns
from apps.professionals.urls import management_urlpatterns as professional_management_urlpatterns
from apps.verification.full_check_api import VerificationSettingView, NotificationView
from apps.site_capture.full_check_api import PublicMapLayerView
from apps.verification.outbox import VerificationOutboxView, VerificationNoticeSentView

urlpatterns = [
    path("management/verification-outbox/", VerificationOutboxView.as_view()),
    path("management/verification-outbox/<uuid:notice_id>/sent/", VerificationNoticeSentView.as_view()),
    path("management/map-layers/", PublicMapLayerView.as_view()),
    path("", include("apps.common.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("users/", include("apps.accounts.profile_urls")),
    path("local-official/", include("apps.local_officials.urls")),
    path("localities/", include("apps.localities.urls")),
    path("properties/", include("apps.properties.urls")),
    path("site-captures/", include("apps.site_capture.urls")),
    path("verifications/", include("apps.verification.urls")),
    path("verification-tasks/", include("apps.verification.task_urls")),
    path("professionals/", include("apps.professionals.urls")),
    path("management/professionals/", include((professional_management_urlpatterns, "professionals-management"))),
    path("full-checks/", include("apps.verification.full_check_urls")),
    path("verification-notices/", NotificationView.as_view()),
    path("management/verification-settings/<str:setting_key>/", VerificationSettingView.as_view()),
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
    path("management/local-officials/", include("apps.local_officials.management_urls")),
    path("management/verifications/", include((verification_management_urlpatterns, "management-verifications"))),
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
