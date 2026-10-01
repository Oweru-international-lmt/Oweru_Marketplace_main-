from django.contrib.auth.base_user import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, phone, full_name, password, **extra_fields):
        if not phone:
            raise ValueError("A phone number is required.")
        if not full_name:
            raise ValueError("A full name is required.")
        user = self.model(phone=phone.strip(), full_name=full_name.strip(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, phone, full_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(phone, full_name, password, **extra_fields)

    def create_superuser(self, phone, full_name, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if extra_fields.get("is_staff") is not True or extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusers must have is_staff and is_superuser enabled.")
        return self._create_user(phone, full_name, password, **extra_fields)
