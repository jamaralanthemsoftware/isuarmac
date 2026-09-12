from django import forms
from django.contrib import admin, messages
from django.shortcuts import redirect, render
from django.urls import path

from .models import (
    AnthemCRMIntegration,
    BlogImportItem,
    BlogImportRun,
    BlogPost,
    BlogPostRelatedSelection,
    BlogTopic,
    DownloadableAsset,
    FAQ,
    GoogleServicesIntegration,
    Lead,
    Page,
    PostmarkIntegration,
    RecaptchaIntegration,
    Service,
    SiteSettings,
)
from .blog_importer import MAX_UPLOAD_BYTES, run_import


class BlogImportForm(forms.Form):
    mode = forms.ChoiceField(
        choices=[("wxr", "Upload WordPress WXR XML"), ("sitemap", "Crawl a public sitemap URL")],
        widget=forms.RadioSelect,
    )
    wxr_file = forms.FileField(required=False, label="WordPress WXR XML")
    source_url = forms.URLField(required=False, label="Public sitemap or sitemap-index URL")

    def clean(self):
        cleaned = super().clean()
        mode = cleaned.get("mode")
        upload = cleaned.get("wxr_file")
        source_url = cleaned.get("source_url")
        if mode == "wxr":
            if not upload:
                self.add_error("wxr_file", "Choose a WXR XML file.")
            elif upload.size > MAX_UPLOAD_BYTES:
                self.add_error("wxr_file", "The WXR file exceeds the 10 MB limit.")
        elif mode == "sitemap" and not source_url:
            self.add_error("source_url", "Enter a public sitemap URL.")
        return cleaned


class BlogImportMixin:
    def import_view(self, request):
        if not request.user.is_active or not request.user.is_superuser:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied
        form = BlogImportForm(request.POST or None, request.FILES or None)
        run = None
        if request.method == "POST" and form.is_valid():
            upload = form.cleaned_data.get("wxr_file")
            run = run_import(
                user=request.user,
                mode=form.cleaned_data["mode"],
                payload=upload.read() if upload else None,
                source_url=form.cleaned_data.get("source_url", ""),
                uploaded_name=upload.name if upload else "",
            )
            if run.status == BlogImportRun.Status.FAILED:
                messages.error(request, run.error_summary)
            else:
                messages.success(
                    request,
                    f"Import complete: {run.imported_count} drafts, "
                    f"{run.duplicate_count} duplicates, {run.failed_count} failures.",
                )
        return render(request, "admin/blog_import/import.html", {"form": form, "run": run})

    def get_urls(self):
        urls = super().get_urls()
        return [path("import/", self.admin_site.admin_view(self.import_view), name="blog-import")] + urls

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser


class BlogPostRelatedSelectionInline(admin.TabularInline):
    model = BlogPostRelatedSelection
    fk_name = "source_post"
    autocomplete_fields = ["related_post"]
    extra = 0
    max_num = 3
    fields = ["position", "related_post"]
    verbose_name = "important related article"
    verbose_name_plural = "Important related articles (up to 3)"


@admin.register(BlogPost)
class BlogPostAdmin(BlogImportMixin, admin.ModelAdmin):
    inlines = [BlogPostRelatedSelectionInline]
    list_display = [
        "title", "slug", "is_published", "author_name", "original_published_at", "updated_at",
    ]
    list_filter = ["is_published", "topics", "created_at"]
    search_fields = ["title", "summary", "body", "source_url", "source_guid"]
    filter_horizontal = ["topics"]
    readonly_fields = ["created_at", "updated_at", "word_count"]
    fieldsets = [
        ("Content", {"fields": ["title", "slug", "summary", "body", "word_count", "topics"]}),
        ("Search metadata", {"fields": ["meta_title", "meta_description", "canonical_url"]}),
        ("Imported source", {
            "fields": [
                "source_url", "source_guid", "author_name", "original_published_at",
                "original_modified_at", "featured_image",
            ]
        }),
        ("Publishing", {"fields": ["is_published"]}),
        ("Record details", {"fields": ["created_at", "updated_at"]}),
    ]

    @admin.display(description="Words")
    def word_count(self, obj):
        from django.utils.html import strip_tags
        return len(strip_tags(obj.body).split())

@admin.register(BlogTopic)
class BlogTopicAdmin(admin.ModelAdmin):
    list_display = ["name", "slug", "updated_at"]
    search_fields = ["name"]
    prepopulated_fields = {"slug": ("name",)}
@admin.register(BlogImportRun)
class BlogImportRunAdmin(BlogImportMixin, admin.ModelAdmin):
    list_display = [
        "created_at", "mode", "status", "imported_count", "duplicate_count", "failed_count",
        "created_by",
    ]
    list_filter = ["mode", "status", "created_at"]
    readonly_fields = [
        "mode", "source_url", "uploaded_name", "status", "imported_count", "duplicate_count",
        "failed_count", "error_summary", "limits", "created_by", "started_at", "finished_at",
    ]
    change_form_template = "admin/blog_import/run_change_form.html"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(BlogImportItem)
class BlogImportItemAdmin(admin.ModelAdmin):
    list_display = ["run", "status", "title", "source_url", "error_summary"]
    list_filter = ["status"]
    search_fields = ["title", "source_url", "source_guid", "error_summary"]
    readonly_fields = [field.name for field in BlogImportItem._meta.fields]

    def has_add_permission(self, request):
        return False

    def _superuser_access(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return self._superuser_access(request)

    def has_change_permission(self, request, obj=None):
        return self._superuser_access(request)

    def has_delete_permission(self, request, obj=None):
        return self._superuser_access(request)

    def has_module_permission(self, request):
        return self._superuser_access(request)


@admin.register(SiteSettings)
class SiteSettingsAdmin(admin.ModelAdmin):
    fieldsets = [
        ("Identity", {"fields": ["site_name", "tagline"]}),
        ("Contact", {"fields": ["contact_email", "contact_phone", "address"]}),
        (
            "Search and analytics",
            {
                "fields": [
                    "default_meta_description",
                    "default_open_graph_title",
                    "default_open_graph_description",
                    "default_open_graph_image",
                    "analytics_measurement_id",
                ]
            },
        ),
        ("Legal", {"fields": ["footer_disclaimer"]}),
    ]

    def has_add_permission(self, request):
        return not SiteSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class RecaptchaIntegrationAdminForm(forms.ModelForm):
    secret_key = forms.CharField(
        required=False,
        strip=True,
        widget=forms.PasswordInput(render_value=False),
        help_text=(
            "Enter a new Google reCAPTCHA secret key to save it encrypted. "
            "Leave blank to keep the existing key."
        ),
    )

    class Meta:
        model = RecaptchaIntegration
        fields = [
            "site_key",
            "secret_key",
            "minimum_score",
            "allowed_hostnames",
            "is_enabled",
        ]

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("is_enabled"):
            return cleaned_data

        if not cleaned_data.get("site_key"):
            self.add_error("site_key", "Enter the permanent domain's site key.")
        if not cleaned_data.get("allowed_hostnames", "").strip():
            self.add_error(
                "allowed_hostnames",
                "Enter at least one permanent hostname.",
            )
        if not cleaned_data.get("secret_key") and not self.instance.secret_key_configured:
            self.add_error(
                "secret_key",
                "Enter the permanent domain's secret key before enabling reCAPTCHA.",
            )
        return cleaned_data

    def save(self, commit=True):
        integration = super().save(commit=False)
        secret_key = self.cleaned_data.get("secret_key")
        if secret_key:
            integration.set_secret_key(secret_key)
        if commit:
            integration.save()
        return integration


@admin.register(RecaptchaIntegration)
class RecaptchaIntegrationAdmin(admin.ModelAdmin):
    form = RecaptchaIntegrationAdminForm
    list_display = [
        "__str__",
        "is_enabled",
        "minimum_score",
        "secret_key_configured",
        "updated_at",
    ]
    readonly_fields = ["secret_key_configured", "created_at", "updated_at"]
    fieldsets = [
        (
            "Permanent domain credentials",
            {
                "fields": [
                    "site_key",
                    "secret_key",
                    "secret_key_configured",
                    "allowed_hostnames",
                ]
            },
        ),
        ("Verification", {"fields": ["minimum_score", "is_enabled"]}),
        ("Record details", {"fields": ["created_at", "updated_at"]}),
    ]

    def has_add_permission(self, request):
        return not RecaptchaIntegration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


class PostmarkIntegrationAdminForm(forms.ModelForm):
    server_api_token = forms.CharField(
        required=False,
        strip=True,
        max_length=512,
        widget=forms.PasswordInput(render_value=False),
        help_text=(
            "Enter a new Postmark Server API token to save it encrypted. "
            "Leave blank to keep the existing token."
        ),
    )

    class Meta:
        model = PostmarkIntegration
        fields = [
            "from_email",
            "recipient_emails",
            "message_stream",
            "server_api_token",
            "is_enabled",
        ]

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get("is_enabled"):
            return cleaned_data

        if not cleaned_data.get("from_email"):
            self.add_error(
                "from_email",
                "Enter a sender address verified in Postmark.",
            )
        if not cleaned_data.get("recipient_emails", "").strip():
            self.add_error(
                "recipient_emails",
                "Enter at least one form-submission recipient.",
            )
        if not cleaned_data.get("message_stream", "").strip():
            self.add_error("message_stream", "Enter a Postmark message stream.")
        if (
            not cleaned_data.get("server_api_token")
            and not self.instance.server_api_token_configured
        ):
            self.add_error(
                "server_api_token",
                "Enter the Postmark Server API token before enabling delivery.",
            )
        return cleaned_data

    def save(self, commit=True):
        integration = super().save(commit=False)
        server_api_token = self.cleaned_data.get("server_api_token")
        if server_api_token:
            integration.set_server_api_token(server_api_token)
        if commit:
            integration.save()
        return integration


@admin.register(PostmarkIntegration)
class PostmarkIntegrationAdmin(admin.ModelAdmin):
    form = PostmarkIntegrationAdminForm
    list_display = [
        "__str__",
        "is_enabled",
        "from_email",
        "server_api_token_configured",
        "updated_at",
    ]
    readonly_fields = [
        "server_api_token_configured",
        "created_at",
        "updated_at",
    ]
    fieldsets = [
        (
            "Form delivery",
            {
                "fields": [
                    "from_email",
                    "recipient_emails",
                    "message_stream",
                ]
            },
        ),
        (
            "Postmark credentials",
            {
                "fields": [
                    "server_api_token",
                    "server_api_token_configured",
                    "is_enabled",
                ]
            },
        ),
        ("Record details", {"fields": ["created_at", "updated_at"]}),
    ]

    def has_add_permission(self, request):
        return not PostmarkIntegration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(GoogleServicesIntegration)
class GoogleServicesIntegrationAdmin(admin.ModelAdmin):
    def changelist_view(self, request, extra_context=None):
        return redirect("google-services-dashboard")

    def has_module_permission(self, request):
        return request.user.is_active and request.user.is_superuser

    def has_view_permission(self, request, obj=None):
        return request.user.is_active and request.user.is_superuser

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class AnthemCRMIntegrationAdminForm(forms.ModelForm):
    webhook_url = forms.URLField(
        required=False,
        max_length=500,
        widget=forms.PasswordInput(render_value=False),
        help_text=(
            "Enter the client-specific Anthem CRM webhook URL to save it encrypted. "
            "Leave blank to keep the existing URL."
        ),
    )

    class Meta:
        model = AnthemCRMIntegration
        fields = ["webhook_url", "is_enabled"]

    def clean_webhook_url(self):
        webhook_url = self.cleaned_data.get("webhook_url", "")
        if webhook_url:
            from .models import validate_anthem_webhook_url

            validate_anthem_webhook_url(webhook_url)
        return webhook_url

    def clean(self):
        cleaned_data = super().clean()
        if (
            cleaned_data.get("is_enabled")
            and not cleaned_data.get("webhook_url")
            and not self.instance.webhook_url_configured
        ):
            self.add_error(
                "webhook_url",
                "Enter a valid Anthem CRM webhook before enabling delivery.",
            )
        return cleaned_data

    def save(self, commit=True):
        integration = super().save(commit=False)
        webhook_url = self.cleaned_data.get("webhook_url")
        if webhook_url:
            integration.set_webhook_url(webhook_url)
        if commit:
            integration.save()
        return integration


@admin.register(AnthemCRMIntegration)
class AnthemCRMIntegrationAdmin(admin.ModelAdmin):
    form = AnthemCRMIntegrationAdminForm
    list_display = [
        "__str__",
        "is_enabled",
        "webhook_url_configured",
        "updated_at",
    ]
    readonly_fields = [
        "webhook_url_configured",
        "created_at",
        "updated_at",
    ]
    fieldsets = [
        (
            "CRM webhook",
            {
                "fields": [
                    "webhook_url",
                    "webhook_url_configured",
                    "is_enabled",
                ]
            },
        ),
        ("Record details", {"fields": ["created_at", "updated_at"]}),
    ]

    def has_add_permission(self, request):
        return not AnthemCRMIntegration.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Page)
class PageAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_published", "show_in_navigation", "updated_at"]
    list_filter = ["is_published", "show_in_navigation"]
    search_fields = ["title", "summary", "body"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["word_count"]
    fieldsets = [
        ("Content", {"fields": ["title", "slug", "summary", "body", "word_count"]}),
        (
            "Search and social sharing",
            {
                "fields": [
                    "meta_title",
                    "meta_description",
                    "open_graph_title",
                    "open_graph_description",
                    "open_graph_image",
                ]
            },
        ),
        (
            "Publishing",
            {"fields": ["is_published", "published_at", "show_in_navigation", "navigation_order"]},
        ),
    ]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_published", "display_order", "updated_at"]
    list_filter = ["is_published"]
    search_fields = ["title", "summary", "body"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["word_count"]
    fieldsets = [
        ("Content", {"fields": ["title", "slug", "summary", "body", "word_count"]}),
        (
            "Search and social sharing",
            {
                "fields": [
                    "meta_title",
                    "meta_description",
                    "open_graph_title",
                    "open_graph_description",
                    "open_graph_image",
                ]
            },
        ),
        (
            "Call to action",
            {"fields": ["call_to_action_label", "call_to_action_url"]},
        ),
        (
            "Publishing",
            {"fields": ["is_published", "published_at", "display_order"]},
        ),
    ]


@admin.register(FAQ)
class FAQAdmin(admin.ModelAdmin):
    list_display = ["question", "is_published", "display_order", "updated_at"]
    list_filter = ["is_published"]
    list_editable = ["is_published", "display_order"]
    search_fields = ["question", "answer"]


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = [
        "first_name",
        "last_name",
        "email",
        "status",
        "anthem_delivery_status",
        "source",
        "created_at",
    ]
    list_filter = [
        "status",
        "anthem_delivery_status",
        "consent_to_contact",
        "created_at",
    ]
    search_fields = [
        "first_name",
        "last_name",
        "email",
        "phone",
        "message",
    ]
    readonly_fields = [
        "anthem_delivery_status",
        "anthem_attempted_at",
        "anthem_http_status",
        "anthem_error_summary",
        "anthem_record_identifier",
        "created_at",
        "updated_at",
    ]


@admin.register(DownloadableAsset)
class DownloadableAssetAdmin(admin.ModelAdmin):
    list_display = ["title", "slug", "is_published", "updated_at"]
    list_filter = ["is_published"]
    prepopulated_fields = {"slug": ("title",)}
