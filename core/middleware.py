from django.conf import settings


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
        ):
            if private_prefix != "//" and (
                request.path == private_prefix.rstrip("/")
                or request.path.startswith(private_prefix)
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