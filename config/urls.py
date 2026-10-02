from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenRefreshView

urlpatterns = [
    path("api/<str:version>/management/authorization/", include("authorization.urls")),
    path("admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="api-docs"),
    path("api/<str:version>/", include("core.urls")),
    path("api/<str:version>/auth/", include("accounts.urls")),
    path("api/<str:version>/auth/token/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
]
