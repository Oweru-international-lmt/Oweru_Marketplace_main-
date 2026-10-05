from django.contrib import admin

from .models import PossibleDuplicate, PropertyRecord


@admin.register(PropertyRecord)
class PropertyRecordAdmin(admin.ModelAdmin):
    list_display = ("property_id", "category", "locality", "stated_size", "size_unit", "title_type", "created_by", "created_at")
    list_filter = ("category", "title_type", "region", "district", "ward")
    search_fields = ("property_id", "locality__name", "ward__name", "district__name", "region__name")
    readonly_fields = ("id", "created_at", "updated_at", "created_by")
    actions = None

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PossibleDuplicate)
class PossibleDuplicateAdmin(admin.ModelAdmin):
    list_display = ("id", "property_a", "property_b", "status", "signals", "reviewed_by", "reviewed_at", "created_at")
    list_filter = ("status", "created_at", "reviewed_at")
    search_fields = ("property_a__property_id", "property_b__property_id")
    readonly_fields = ("id", "created_at", "updated_at")
    actions = None

    def has_delete_permission(self, request, obj=None):
        return False
