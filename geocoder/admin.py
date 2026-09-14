from django.contrib import admin

from .models import Geocache


@admin.register(Geocache)
class GeocacheAdmin(admin.ModelAdmin):
    list_display = [
        'address',
        'lat',
        'lon',
        'updated_at',
    ]
    search_fields = [
        'address',
    ]
    readonly_fields = [
        'updated_at',
    ]
