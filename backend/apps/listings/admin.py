from django.contrib import admin

from .models import Listing, ListingPhoto


class ListingPhotoInline(admin.TabularInline):
    model = ListingPhoto
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")
    fields = ("id", "media", "position", "created_at", "updated_at")


@admin.register(Listing)
class ListingAdmin(admin.ModelAdmin):
    list_display = ("listing_id", "property", "lister", "lister_kind", "selling_price", "currency", "status", "created_at")
    list_filter = ("lister_kind", "currency", "status")
    search_fields = ("listing_id", "property__property_id", "lister__email", "lister__phone", "lister__full_name")
    readonly_fields = ("id", "created_at", "updated_at")
    inlines = [ListingPhotoInline]
    actions = None

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ListingPhoto)
class ListingPhotoAdmin(admin.ModelAdmin):
    list_display = ("id", "listing", "media", "position", "created_at")
    list_filter = ("created_at",)
    search_fields = ("listing__listing_id", "media__media_id")
    readonly_fields = ("id", "created_at", "updated_at")
