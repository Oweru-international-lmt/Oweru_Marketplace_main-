from django.contrib import admin

from .models import District, Locality, Region, Ward


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ("name", "created_at", "updated_at")
    search_fields = ("name",)


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ("name", "region", "created_at", "updated_at")
    list_filter = ("region",)
    search_fields = ("name", "region__name")


@admin.register(Ward)
class WardAdmin(admin.ModelAdmin):
    list_display = ("name", "district", "created_at", "updated_at")
    list_filter = ("district__region", "district")
    search_fields = ("name", "district__name", "district__region__name")


@admin.register(Locality)
class LocalityAdmin(admin.ModelAdmin):
    list_display = ("name", "kind", "ward", "approved", "created_by", "created_at", "updated_at")
    list_filter = ("kind", "approved", "ward__district__region", "ward__district", "ward")
    search_fields = ("name", "ward__name", "ward__district__name", "ward__district__region__name")
    readonly_fields = ("created_by",)
