from .models import Page, SiteSettings


def site_settings(request):
    settings_record = SiteSettings.objects.first()
    navigation_pages = Page.objects.filter(is_published=True, show_in_navigation=True)
    return {
        "site_settings": settings_record,
        "navigation_pages": navigation_pages,
    }
