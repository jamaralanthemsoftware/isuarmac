from urllib.parse import urlsplit

from django import template
from django.conf import settings
from django.utils.html import conditional_escape, format_html

from core.image_pipeline import image_dimensions, responsive_renditions

register = template.Library()


@register.inclusion_tag("includes/responsive_image.html")
def responsive_image(image, alt="", lcp=False, sizes="100vw", class_name=""):
    """Render an accessible responsive image with stable intrinsic dimensions."""
    if not image:
        return {"image": None}
    try:
        renditions = responsive_renditions(image)
        width, height = image_dimensions(image)
    except (OSError, ValueError, TypeError):
        return {"image": None}
    if not renditions:
        return {"image": None}
    return {
        "image": image,
        "src": renditions[-1].url,
        "srcset": ", ".join(f"{item.url} {item.width}w" for item in renditions),
        "width": width,
        "height": height,
        "alt": conditional_escape(alt),
        "sizes": sizes,
        "class_name": class_name,
        "loading": "eager" if lcp else "lazy",
        "fetchpriority": "high" if lcp else "auto",
    }


@register.simple_tag
def third_party_script(src, service="third-party"):
    """Return an opt-in deferred script; callers choose where this tag is used."""
    parsed = urlsplit(str(src))
    if (
        parsed.scheme.lower() != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
    ):
        raise ValueError("Third-party scripts require a credential-free HTTPS URL.")
    try:
        origin = f"https://{parsed.hostname.lower()}"
        if parsed.port:
            origin += f":{parsed.port}"
    except ValueError as exc:
        raise ValueError("Third-party script URL has an invalid port.") from exc
    allowed_origins = {
        str(value).rstrip("/").lower()
        for value in getattr(settings, "THIRD_PARTY_SCRIPT_ORIGINS", set())
    }
    if not allowed_origins or origin not in allowed_origins:
        raise ValueError("Third-party script origin is not approved.")
    return format_html(
        '<script src="{}" data-third-party="{}" defer></script>',
        src,
        service,
    )