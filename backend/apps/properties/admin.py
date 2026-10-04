from django.contrib import admin

from .models import PropertyRecord


@admin.register(PropertyRecord)
class PropertyRecordAdmin(admin.ModelAdmin):
    list_display = ("property_id", "category", "locality", "stated_size", "size_unit", "title_type", "created_by", "created_at")
    list_filter = ("category", "title_type", "region", "district", "ward")
    search_fields = ("property_id", "locality__name", "ward__name", "district__name", "region__name")
    readonly_fields = ("id", "created_at", "updated_at", "created_by")
    actions = None

    def has_delete_permission(self, request, obj=None):
        return False
