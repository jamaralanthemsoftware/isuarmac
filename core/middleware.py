from django.conf import settings
from django.http import HttpResponsePermanentRedirect

LEGACY_WORDPRESS_REDIRECTS = {
    "/staff/": "/our-team/",
    "/tell-a-friend/": "/refer-a-friend/",
    "/welcome-to-insurance-company/": "/",
    "/service/": "/insurance-center/service/",
    "/service/flood-insurance/": "/insurance-center/service/personal-lines-insurance/flood-insurance/",
    "/service/vacant-land-insurance/": "/insurance-center/service/commercial-insurance/vacant-land-insurance/",
    "/service/boat-insurance/": "/insurance-center/service/personal-lines-insurance/boat-insurance/",
    "/service/motorcycle-insurance/": "/insurance-center/service/personal-lines-insurance/motorcycle-insurance/",
    "/service/annuities/": "/annuities/",
    "/service/high-fire-risk-insurance/": "/insurance-center/service/private-client-insurance/high-fire-risk-insurance/",
    "/service/watercraft-insurance/": "/insurance-center/service/personal-lines-insurance/boat-insurance/",
    "/service/umbrella-insurance/": "/insurance-center/service/private-client-insurance/umbrella-insurance/",
    "/service/valuable-possessions-insurance/": "/insurance-center/service/private-client-insurance/valuable-possessions-insurance/",
    "/service/secondary-home-insurance/": "/insurance-center/service/private-client-insurance/secondary-home-insurance/",
    "/service/renters-insurance/": "/insurance-center/service/private-client-insurance/renters-insurance/",
    "/service/individual-life-insurance/": "/insurance-center/service/private-client-insurance/individual-life-insurance/",
    "/service/high-net-worth-insurance/": "/insurance-center/service/private-client-insurance/high-net-worth-insurance/",
    "/service/life-insurance/": "/insurance-center/service/private-client-insurance/individual-life-insurance/",
    "/service/business-insurance/": "/insurance-center/service/commercial-insurance/",
    "/service/home-insurance/": "/insurance-center/service/personal-lines-insurance/home-insurance/",
    "/service/health-insurance/": "/insurance-center/products/health-insurance/",
}


class LegacyUploadsRedirectMiddleware:
    """Old WordPress image links (/wp-content/uploads/...) and retired paths keep working."""

    PREFIX = "/wp-content/uploads/"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith(self.PREFIX):
            return HttpResponsePermanentRedirect(
                "/media/uploads/" + request.path[len(self.PREFIX):]
            )
        target = LEGACY_WORDPRESS_REDIRECTS.get(request.path)
        if target:
            return HttpResponsePermanentRedirect(target)
        return self.get_response(request)


class PublicPageCacheMiddleware:
    """Add shared-cache headers only to anonymous, cookie-free public GET/HEAD pages."""

    cache_control = "public, max-age=60, s-maxage=300, stale-while-revalidate=86400"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if self._cacheable(request, response):
            response.headers["Cache-Control"] = self.cache_control
        return response

    @staticmethod
    def _cacheable(request, response):
        if request.method not in {"GET", "HEAD"} or not 200 <= response.status_code < 300:
            return False
        if request.path.startswith("/static/") or request.path.startswith("/media/"):
            return False
        admin_url = "/" + str(getattr(settings, "ADMIN_URL", "admin/")).strip("/") + "/"
        if request.path == admin_url.rstrip("/") or request.path.startswith(admin_url):
            return False
        for private_prefix in (
            "/" + str(getattr(settings, "ADMIN_LOCAL_LOGIN_URL", "")).strip("/") + "/",
            "/accounts/",
            "/api/",
            "/integrations/",
            "/downloads/",
            "/healthz/",
        ):
            if private_prefix != "//" and (
                request.path == private_prefix.rstrip("/")
                or request.path.startswith(private_prefix)
            ):
                return False
        if (
            getattr(request, "headers", {}).get("Authorization")
            or getattr(request, "META", {}).get("HTTP_AUTHORIZATION")
        ):
            return False
        if getattr(request, "user", None) is not None and request.user.is_authenticated:
            return False
        session = getattr(request, "session", None)
        if (
            getattr(request, "COOKIES", None)
            or getattr(request, "META", {}).get("HTTP_COOKIE")
            or (
                session is not None
                and session.modified
            )
        ):
            return False
        if response.cookies or "cookie" in response.get("Vary", "").lower():
            return False
        existing = response.get("Cache-Control", "").lower()
        if any(value in existing for value in ("private", "no-cache", "no-store")):
            return False
        return True