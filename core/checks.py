from django.conf import settings
from django.core.checks import Error, register

from .google_services import settings_error


@register()
def check_google_services_oauth(app_configs, **kwargs):
    values = (
        settings.GOOGLE_SERVICES_OAUTH_CLIENT_ID,
        settings.GOOGLE_SERVICES_OAUTH_CLIENT_SECRET,
        settings.GOOGLE_SERVICES_ENCRYPTION_KEY,
    )
    if not any(values):
        return []
    error = settings_error()
    if not error:
        return []
    return [
        Error(
            error,
            hint=(
                "Configure all Google services OAuth secrets and register the "
                "exact callback URI before connecting GA4 or Search Console."
            ),
            id="core.E003",
        )
    ]