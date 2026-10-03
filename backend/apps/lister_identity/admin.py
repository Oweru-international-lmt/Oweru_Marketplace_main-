from django.contrib import admin

from .models import ListerIdentity


@admin.register(ListerIdentity)
class ListerIdentityAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "status", "submitted_at", "reviewed_at", "expires_at", "created_at")
    list_filter = ("status",)
    search_fields = ("id", "user__email", "user__phone", "user__full_name")
    readonly_fields = ("id", "created_at", "updated_at")
