import pytest
from django.contrib.auth import get_user_model


pytestmark = pytest.mark.django_db


def test_user_manager_creates_email_login_user_with_normalized_required_fields():
    User = get_user_model()

    user = User.objects.create_user(
        email="  ASHA@Example.TEST ",
        phone="  +255700123456 ",
        full_name="  Asha Mushi ",
        password="Strong-pass-482!",
    )

    assert user.email == "asha@example.test"
    assert user.phone == "+255700123456"
    assert user.full_name == "Asha Mushi"
    assert user.preferred_language == User.Language.SWAHILI
    assert user.USERNAME_FIELD == "email"
    assert user.check_password("Strong-pass-482!")
    assert user.is_active
    assert not user.is_staff
    assert user.date_joined is not None


def test_user_manager_rejects_missing_required_identity_fields():
    User = get_user_model()

    with pytest.raises(ValueError):
        User.objects.create_user(email="", phone="+255700123456", full_name="Asha", password="x")
    with pytest.raises(ValueError):
        User.objects.create_user(email="asha@example.test", phone="", full_name="Asha", password="x")
    with pytest.raises(ValueError):
        User.objects.create_user(email="asha@example.test", phone="+255700123456", full_name="", password="x")
    with pytest.raises(ValueError):
        User.objects.create_user(email="asha@example.test", phone="+255700123456", full_name="   ", password="x")


@pytest.mark.parametrize("password", [None, "", "   "])
def test_user_manager_rejects_missing_or_blank_password(password):
    User = get_user_model()

    with pytest.raises(ValueError):
        User.objects.create_user(
            email="asha@example.test",
            phone="+255700123456",
            full_name="Asha Mushi",
            password=password,
        )


def test_superuser_flags_and_email_normalization():
    User = get_user_model()

    user = User.objects.create_superuser(
        email="ADMIN@Example.TEST",
        phone="+255700000000",
        full_name="Admin User",
        password="Strong-pass-482!",
    )

    assert user.email == "admin@example.test"
    assert user.is_staff
    assert user.is_superuser
    assert user.is_active


def test_natural_key_lookup_is_case_insensitive():
    User = get_user_model()
    user = User.objects.create_user(
        email="asha@example.test",
        phone="+255700123456",
        full_name="Asha Mushi",
        password="Strong-pass-482!",
    )

    assert User.objects.get_by_natural_key("ASHA@Example.TEST") == user
