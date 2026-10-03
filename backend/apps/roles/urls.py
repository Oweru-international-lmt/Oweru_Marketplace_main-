from django.urls import include, path

urlpatterns = [
    path("", include("apps.roles.legacy_authorization.urls")),
]
