from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("", include("apps.common.urls")),
    path("auth/", include("apps.accounts.urls")),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("users/", include("apps.accounts.profile_urls")),
    path("localities/", include("apps.localities.urls")),
    path("properties/", include("apps.properties.urls")),
    path("lister-identity/", include("apps.lister_identity.urls")),
    path("listers/", include("apps.lister_identity.public_urls")),
    path("management/lister-identities/", include("apps.lister_identity.management_urls")),
    path("management/authorization/", include("apps.roles.urls")),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="api-redoc"),
]
