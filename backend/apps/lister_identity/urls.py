from django.urls import path

from .views import ListerIdentityCreateView, ListerIdentityMeView, ListerIdentitySubmitView


urlpatterns = [
    path("", ListerIdentityCreateView.as_view(), name="lister-identity-create"),
    path("me/", ListerIdentityMeView.as_view(), name="lister-identity-me"),
    path("me/submit/", ListerIdentitySubmitView.as_view(), name="lister-identity-submit"),
]
