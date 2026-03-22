from django.contrib import admin

from authentication.models import APIKey


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ["name", "is_active", "created_at", "last_used_at"]
    list_filter = ["is_active"]
    readonly_fields = ["id", "key_hash", "created_at", "last_used_at"]
    search_fields = ["name"]
