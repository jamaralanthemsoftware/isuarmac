from django import template

register = template.Library()


@register.inclusion_tag("menu/breadcrumb.html", takes_context=True)
def page_breadcrumb(context):
    """Home > ancestors > current page, from the CMS page tree (pages are not menu entries)."""
    request = context.get("request")
    page = getattr(request, "current_page", None)
    crumbs = [("Home", "/")]
    if page and not page.is_home:
        for ancestor in page.get_ancestor_pages():
            if ancestor.is_home:
                continue
            content = ancestor.get_content_obj("en")
            if content:
                crumbs.append((content.menu_title or content.title, ancestor.get_absolute_url("en")))
        content = page.get_content_obj("en")
        crumbs.append((content.menu_title or content.title if content else "", None))
    return {"crumbs": crumbs}
