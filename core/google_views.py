import secrets
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.views import redirect_to_login
from django.http import HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .google_services import (
    GOOGLE_SERVICES_SCOPES,
    GoogleServicesError,
    authenticated_email,
    authorization_url,
    create_pkce,
    decrypt_refresh_token,
    encrypt_refresh_token,
    exchange_code,
    revoke_refresh_token,
    settings_ready,
)
from .models import GoogleServicesIntegration


def superuser_required(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(
                request.get_full_path(),
                f"/{settings.ADMIN_URL}login/",
            )
        if not request.user.is_active or not request.user.is_superuser:
            return HttpResponseForbidden("Superuser access required.")
        return view(request, *args, **kwargs)

    return never_cache(wrapped)


def integration():
    return GoogleServicesIntegration.objects.filter(
        singleton_key="default"
    ).first()


@superuser_required
@require_GET
def dashboard(request):
    record = integration()
    token_error = ""
    if record and record.refresh_token_encrypted:
        try:
            decrypt_refresh_token(record.refresh_token_encrypted)
        except GoogleServicesError as error:
            token_error = str(error)
    return render(
        request,
        "admin/google_services/dashboard.html",
        {
            "integration": record,
            "settings_ready": settings_ready(),
            "callback_uri": settings.GOOGLE_SERVICES_CALLBACK_URI,
            "scopes": GOOGLE_SERVICES_SCOPES,
            "token_error": token_error,
        },
    )


@superuser_required
@require_POST
def connect(request):
    if not settings_ready():
        return HttpResponse(
            "Google services OAuth settings are not configured.",
            status=503,
        )
    record = integration()
    if record and record.refresh_token_encrypted:
        return HttpResponse(
            "Disconnect the existing Google services connection before reconnecting.",
            status=409,
        )
    state = secrets.token_urlsafe(32)
    verifier, challenge = create_pkce()
    request.session["google_services_oauth"] = {
        "state": state,
        "verifier": verifier,
    }
    return redirect(authorization_url(state, challenge))


@superuser_required
@require_GET
def callback(request):
    saved = request.session.get("google_services_oauth") or {}
    state = request.GET.get("state", "")
    saved_state = saved.get("state", "")
    if (
        not saved
        or not state
        or not saved_state
        or not secrets.compare_digest(state, saved_state)
    ):
        return HttpResponse("Invalid OAuth state.", status=400)
    request.session.pop("google_services_oauth", None)
    if request.GET.get("error"):
        return HttpResponse(
            "Google authorization was not completed.",
            status=400,
        )
    existing = integration()
    if existing and existing.refresh_token_encrypted:
        return HttpResponse(
            "A Google services connection already exists. Disconnect it first.",
            status=409,
        )
    try:
        token = exchange_code(
            request.GET.get("code", ""),
            saved.get("verifier", ""),
        )
        access_token = token.get("access_token")
        scopes = token.get("scope", "")
        granted_scopes = set(scopes.split()) if isinstance(scopes, str) else set()
        missing_scopes = set(GOOGLE_SERVICES_SCOPES) - granted_scopes
        if missing_scopes:
            raise GoogleServicesError(
                "Google did not grant all required Analytics and Search Console permissions."
            )
        email = authenticated_email(access_token)
        refresh_token = token.get("refresh_token")
        if not refresh_token:
            raise GoogleServicesError(
                "Google did not return a refresh token."
            )
        encrypted_refresh_token = encrypt_refresh_token(refresh_token)
        record = existing or GoogleServicesIntegration()
        record.refresh_token_encrypted = encrypted_refresh_token
        record.connected_email = email
        record.authorized_scopes = scopes
        record.connected_at = timezone.now()
        record.full_clean()
        record.save()
    except GoogleServicesError as error:
        return HttpResponse(str(error), status=400)
    messages.success(
        request,
        "Google Analytics and Search Console authorization is connected.",
    )
    return redirect("google-services-dashboard")


@superuser_required
@require_POST
def disconnect(request):
    record = integration()
    if record:
        if not record.refresh_token_encrypted:
            record.delete()
            messages.success(
                request,
                "The incomplete Google services connection was removed.",
            )
            return redirect("google-services-dashboard")
        try:
            revoke_refresh_token(
                decrypt_refresh_token(record.refresh_token_encrypted)
            )
        except GoogleServicesError as error:
            return HttpResponse(
                f"Google could not be disconnected. The connection was preserved so you can retry. {error}",
                status=502,
            )
        record.delete()
    messages.success(
        request,
        "Google Analytics and Search Console authorization was disconnected.",
    )
    return redirect("google-services-dashboard")