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


def site_info(request):
    return {
        "main_menu": MAIN_MENU,
        "footer_columns": FOOTER_COLUMNS,
        "legal_links": LEGAL_LINKS,
        "site": SITE_INFO,
        "active_section": _active_section(request.path),
    }
