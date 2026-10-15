from urllib.parse import urlencode

from django.conf import settings
from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.debug import sensitive_post_parameters


@never_cache
def admin_sso_login(request):
    if not settings.ENABLE_GOOGLE_ADMIN_SSO:
        return admin.site.login(request)

    next_url = request.GET.get("next") or ""
    if not url_has_allowed_host_and_scheme(
        url=next_url,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        next_url = reverse("admin:index")
    query = urlencode({"process": "login", "next": next_url})
    return redirect(f"{reverse('google_login')}?{query}")


@sensitive_post_parameters()
@never_cache
def emergency_admin_login(request):
    """Local-password entry point reserved for the break-glass superuser."""
    return admin.site.login(request)
