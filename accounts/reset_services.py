from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from .models import User


def send_reset_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    separator = "&" if "?" in settings.PASSWORD_RESET_URL else "?"
    link = f"{settings.PASSWORD_RESET_URL}{separator}uid={uid}&token={token}"
    send_mail(
        subject="Reset your Oweru Marketplace password",
        message=f"Use this link to reset your password: {link}",
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=False,
    )


def reset_password(uid, token, new_password):
    try:
        user_id = force_str(urlsafe_base64_decode(uid))
        user = User.objects.get(pk=user_id, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return False
    if not default_token_generator.check_token(user, token):
        return False
    user.set_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None
    user.save(update_fields=["password", "failed_login_attempts", "locked_until", "updated_at"])
    return True
