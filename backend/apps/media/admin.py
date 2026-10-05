from django.contrib import admin

from apps.media.models import Media, MediaVariant


class MediaVariantInline(admin.TabularInline):
    model = MediaVariant
    extra = 0
    readonly_fields = ("id", "created_at", "updated_at")
    fields = ("id", "kind", "file_key", "mime_type", "size_bytes", "width", "height", "created_at", "updated_at")


@admin.register(Media)
class MediaAdmin(admin.ModelAdmin):
    list_display = ("media_id", "content_type", "object_id", "source", "mime_type", "size_bytes", "created_at")
    list_filter = ("source", "mime_type", "content_type", "created_at")
    search_fields = ("media_id", "file_key", "file_hash", "object_id")
    readonly_fields = ("id", "media_id", "created_at", "updated_at")
    inlines = [MediaVariantInline]
    fields = (
        "id",
        "media_id",
        "content_type",
        "object_id",
        "uploaded_by",
        "file_key",
        "source",
        "captured_at",
        "captured_location",
        "device",
        "file_hash",
        "mime_type",
        "size_bytes",
        "created_at",
        "updated_at",
    )
