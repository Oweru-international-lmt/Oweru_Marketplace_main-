from rest_framework.exceptions import PermissionDenied
from rest_framework_simplejwt.authentication import JWTAuthentication

# While a temporary password is in force (ACC-06), the account may only read
# its profile, change its password and sign out.
ALLOWED_WHILE_PASSWORD_CHANGE_REQUIRED = frozenset({"current-user", "password-change", "logout"})


class PasswordChangeRequired(PermissionDenied):
    default_detail = "You must change your temporary password before continuing."
    default_code = "password_change_required"


class MarketplaceJWTAuthentication(JWTAuthentication):
    def authenticate(self, request):
        result = super().authenticate(request)
        if result is not None and result[0].must_change_password:
            match = getattr(request._request, "resolver_match", None)
            if match is None or match.url_name not in ALLOWED_WHILE_PASSWORD_CHANGE_REQUIRED:
                raise PasswordChangeRequired()
        return result
