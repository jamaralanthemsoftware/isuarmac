from django.conf import settings

from anthem_seo.resolver import resolve_request_overrides
from .models import Page, SiteSettings
from .navigation import FOOTER_COLUMNS, LEGAL_LINKS, MAIN_MENU, SITE_INFO


def _active_section(path):
    """The menu section that owns this URL: an exact link match first, then the longest landing-URL prefix."""
    for section in MAIN_MENU:
        if any(url == path for _, url in section["links"]):
            return section["label"]
    best, best_len = None, 0
    for section in MAIN_MENU:
        url = section["url"]
        if path.startswith(url) and len(url) > best_len:
            best, best_len = section["label"], len(url)
    return best


def site_settings(request):
    settings_record = SiteSettings.objects.first() or SiteSettings(
        site_name=SITE_INFO["name"],
        contact_email=SITE_INFO["email"],
        contact_phone=SITE_INFO["phone_ca"],
        address="\n".join(SITE_INFO["address_lines"]),
    )
    navigation_pages = Page.objects.filter(
        is_published=True,
        show_in_navigation=True,
    ).exclude(slug__in={"about", *Page.RESERVED_SLUGS})
    return {
        "site_settings": settings_record,
        "navigation_pages": navigation_pages,
        "analytics_consent_required": settings.ANALYTICS_CONSENT_REQUIRED,
        "main_menu": MAIN_MENU,
        "footer_columns": FOOTER_COLUMNS,
        "legal_links": LEGAL_LINKS,
        "site": SITE_INFO,
        "active_section": _active_section(request.path),
        **resolve_request_overrides(request),
    }
