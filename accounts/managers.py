from django.contrib.auth.base_user import BaseUserManager


def normalize_email_address(email):
    """Trim and lowercase the whole address so one mailbox maps to one account."""
    return (email or "").strip().lower()


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, phone, full_name, password, **extra_fields):
        email = normalize_email_address(email)
        if not email:
            raise ValueError("An email address is required.")
        if not phone:
            raise ValueError("A phone number is required.")
        if not full_name:
            raise ValueError("A full name is required.")
        user = self.model(email=email, phone=phone.strip(), full_name=full_name.strip(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, phone, full_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, phone, full_name, password, **extra_fields)

    def create_superuser(self, email, phone, full_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusers must have is_staff and is_superuser enabled.")
        return self._create_user(email, phone, full_name, password, **extra_fields)

    def get_by_natural_key(self, username):
        return self.get(**{self.model.USERNAME_FIELD: normalize_email_address(username)})
