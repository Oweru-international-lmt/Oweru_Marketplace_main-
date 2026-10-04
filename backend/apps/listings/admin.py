from django.contrib import admin

from .models import Listing


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("listing_id", "property", "lister", "lister_kind", "selling_price", "currency", "status", "created_at")
    list_filter = ("lister_kind", "currency", "status")
    search_fields = ("listing_id", "property__property_id", "lister__email", "lister__phone", "lister__full_name")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = None

    def has_delete_permission(self, request, obj=None):
        return False
