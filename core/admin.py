from django.contrib import admin

from .models import DownloadableAsset, FAQ, Lead, Page, Service, SiteSettings


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Identity", {"fields": ["site_name", "tagline"]}),
        ("Contact", {"fields": ["contact_email", "contact_phone", "address"]}),
        ("Search and analytics", {"fields": ["default_meta_description", "analytics_measurement_id"]}),
        ("Legal", {"fields": ["footer_disclaimer"]}),
    ]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_published", "show_in_navigation", "updated_at"]
    list_filter = ["is_published", "show_in_navigation"]
    search_fields = ["title", "summary", "body"]
    prepopulated_fields = {"slug": ("title",)}


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_published", "display_order", "updated_at"]
    list_filter = ["is_published"]
    search_fields = ["title", "summary", "body"]
    prepopulated_fields = {"slug": ("title",)}


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["question", "is_published", "display_order", "updated_at"]
    list_filter = ["is_published"]
    list_editable = ["is_published", "display_order"]
    search_fields = ["question", "answer"]


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "status", "source", "created_at"]
    list_filter = ["status", "consent_to_contact", "created_at"]
    search_fields = ["name", "email", "phone", "message"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(DownloadableAsset)
class DownloadableAssetAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_published", "updated_at"]
    list_filter = ["is_published"]
    prepopulated_fields = {"slug": ("title",)}
