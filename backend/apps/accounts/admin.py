from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ("email",)
    list_display = ("email", "phone", "full_name", "preferred_language", "is_active", "is_staff")
    list_filter = ("is_active", "is_staff", "is_superuser", "preferred_language")
    search_fields = ("email", "phone", "full_name")
    readonly_fields = ("id", "date_joined", "last_login", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("id", "phone", "full_name", "preferred_language")}),
        ("Status", {"fields": ("is_active", "is_staff", "is_superuser", "date_joined", "last_login")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Important dates", {"fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "phone", "full_name", "preferred_language", "password1", "password2", "is_staff", "is_superuser"),
        }),
    )
