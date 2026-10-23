from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def absolute_url(value, request):
    if not value:
        return ""
    if str(value).startswith(("http://", "https://")):
        return str(value)
    if request is None:
        return str(value)
    return request.build_absolute_uri(value)


@register.inclusion_tag("menu/breadcrumb.html", takes_context=True)
def page_breadcrumb(context):
    """Home > ancestors > current page, from context crumbs or Page.breadcrumb_items."""
    crumbs = [("Home", "/")]
    explicit_crumbs = context.get("crumbs")
    if explicit_crumbs:
        crumbs.extend(explicit_crumbs)
        return {"crumbs": crumbs}
    page = context.get("page") or context.get("object")
    if page is not None and hasattr(page, "breadcrumb_items"):
        if getattr(page, "slug", "") != "home" and getattr(page, "path", "") != "/":
            crumbs.extend(page.breadcrumb_items)
    elif context.get("breadcrumb_title"):
        crumbs.append((context["breadcrumb_title"], None))
    return {"crumbs": crumbs}


@register.simple_tag(takes_context=True)
def render_plugin(context, plugin):
    if plugin is None:
        return ""
    if hasattr(plugin, "render"):
        return mark_safe(plugin.render(context.flatten() if hasattr(context, "flatten") else dict(context)))
    return mark_safe(str(plugin))