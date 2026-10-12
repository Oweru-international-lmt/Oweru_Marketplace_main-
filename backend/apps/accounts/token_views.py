from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from rest_framework_simplejwt.views import TokenRefreshView


class LimitedTokenRefreshView(TokenRefreshView):
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "auth_refresh"
