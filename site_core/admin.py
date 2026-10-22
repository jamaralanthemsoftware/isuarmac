from django.contrib import admin

from .models import BlogCategory, BlogPost, QuoteRequest, TeamMember


@admin.register(QuoteRequest)
class QuoteRequestAdmin(admin.ModelAdmin):
    list_display = ["created", "name", "company", "form_type", "state", "email", "phone", "handled"]
    list_filter = ["form_type", "handled", "state"]
    search_fields = ["name", "company", "email", "phone"]
    list_editable = ["handled"]
    readonly_fields = ["created", "form_type", "page_url", "details"]


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ["name", "title", "order", "featured"]
    list_editable = ["order", "featured"]


@admin.register(BlogCategory)
class BlogCategoryAdmin(admin.ModelAdmin):
    prepopulated_fields = {"slug": ["name"]}


@admin.register(BlogPost)
class BlogPostAdmin(admin.ModelAdmin):
    list_display = ["title", "published", "is_published"]
    list_filter = ["is_published", "categories"]
    search_fields = ["title", "content"]
    prepopulated_fields = {"slug": ["title"]}
    date_hierarchy = "published"
    filter_horizontal = ["categories"]
