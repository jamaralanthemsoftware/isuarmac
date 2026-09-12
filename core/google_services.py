import base64
import hashlib
import json
import secrets
import urllib.parse
import urllib.request
from urllib.error import HTTPError, URLError

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


MAX_RESPONSE_BYTES = 65_536
REQUEST_TIMEOUT_SECONDS = 15
GOOGLE_SERVICES_SCOPES = (
    "openid",
    "email",
    "https://www.googleapis.com/auth/analytics.edit",
    "https://www.googleapis.com/auth/webmasters",
    "https://www.googleapis.com/auth/siteverification",
)


class GoogleServicesError(Exception):
    pass


def settings_error():
    configured = {
        "GOOGLE_SERVICES_OAUTH_CLIENT_ID": (
            settings.GOOGLE_SERVICES_OAUTH_CLIENT_ID
        ),
        "GOOGLE_SERVICES_OAUTH_CLIENT_SECRET": (
            settings.GOOGLE_SERVICES_OAUTH_CLIENT_SECRET
        ),
        "GOOGLE_SERVICES_ENCRYPTION_KEY": (
            settings.GOOGLE_SERVICES_ENCRYPTION_KEY
        ),
        "GOOGLE_SERVICES_CALLBACK_URI": (
            settings.GOOGLE_SERVICES_CALLBACK_URI
        ),
    }
    missing = [name for name, value in configured.items() if not value]
    if missing:
        return "Missing Google services settings: " + ", ".join(missing)
    try:
        Fernet(settings.GOOGLE_SERVICES_ENCRYPTION_KEY.encode())
    except (ValueError, TypeError):
        return "GOOGLE_SERVICES_ENCRYPTION_KEY is not a valid Fernet key."
    callback = urllib.parse.urlsplit(settings.GOOGLE_SERVICES_CALLBACK_URI)
    if not (
        callback.scheme == "https"
        and bool(callback.netloc)
        and callback.path == "/integrations/google/callback/"
        and not callback.query
        and not callback.fragment
    ):
        return (
            "GOOGLE_SERVICES_CALLBACK_URI must be an exact HTTPS URL ending "
            "in /integrations/google/callback/ with no query or fragment."
        )
    return ""


def settings_ready():
    return not settings_error()


def _fernet():
    key = settings.GOOGLE_SERVICES_ENCRYPTION_KEY
    if not key:
        raise GoogleServicesError(
            "GOOGLE_SERVICES_ENCRYPTION_KEY is not configured."
        )
    try:
        return Fernet(key.encode())
    except (ValueError, TypeError):
        raise GoogleServicesError(
            "GOOGLE_SERVICES_ENCRYPTION_KEY is invalid."
        ) from None


def encrypt_refresh_token(token):
    if not isinstance(token, str) or not token:
        raise GoogleServicesError("Google did not return a refresh token.")
    return _fernet().encrypt(token.encode()).decode()


def decrypt_refresh_token(value):
    if not value:
        raise GoogleServicesError("No Google refresh token is stored.")
    try:
        return _fernet().decrypt(value.encode()).decode()
    except (InvalidToken, UnicodeDecodeError, ValueError, TypeError):
        raise GoogleServicesError(
            "The stored Google refresh token cannot be decrypted."
        ) from None


def create_pkce():
    verifier = (
        base64.urlsafe_b64encode(secrets.token_bytes(32))
        .rstrip(b"=")
        .decode()
    )
    challenge = (
        base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        )
        .rstrip(b"=")
        .decode()
    )
    return verifier, challenge


def authorization_url(state, challenge):
    query = urllib.parse.urlencode(
        {
            "client_id": settings.GOOGLE_SERVICES_OAUTH_CLIENT_ID,
            "redirect_uri": settings.GOOGLE_SERVICES_CALLBACK_URI,
            "response_type": "code",
            "scope": " ".join(GOOGLE_SERVICES_SCOPES),
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "access_type": "offline",
            "prompt": "consent",
            "include_granted_scopes": "true",
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def _request(url, data=None, headers=None, method=None):
    request = urllib.request.Request(
        url,
        data=data,
        headers=headers or {},
        method=method or ("POST" if data is not None else "GET"),
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=REQUEST_TIMEOUT_SECONDS,
        ) as response:
            payload = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        raise GoogleServicesError(
            f"Google request failed with HTTP {error.code}."
        ) from None
    except (URLError, TimeoutError, OSError):
        raise GoogleServicesError("Google request failed.") from None
    if len(payload) > MAX_RESPONSE_BYTES:
        raise GoogleServicesError("Google returned an oversized response.")
    if not payload:
        return {}
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, ValueError, TypeError):
        raise GoogleServicesError(
            "Google returned an invalid response."
        ) from None
    if not isinstance(decoded, dict):
        raise GoogleServicesError("Google returned an unexpected response.")
    if "error" in decoded:
        raise GoogleServicesError("Google rejected the request.")
    return decoded


def exchange_code(code, verifier):
    if not code or not verifier:
        raise GoogleServicesError("Google authorization is incomplete.")
    payload = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": settings.GOOGLE_SERVICES_OAUTH_CLIENT_ID,
            "client_secret": settings.GOOGLE_SERVICES_OAUTH_CLIENT_SECRET,
            "redirect_uri": settings.GOOGLE_SERVICES_CALLBACK_URI,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }
    ).encode()
    return _request(
        "https://oauth2.googleapis.com/token",
        payload,
        {"Content-Type": "application/x-www-form-urlencoded"},
    )


def authenticated_email(access_token):
    if not access_token:
        raise GoogleServicesError("Google did not return an access token.")
    result = _request(
        "https://openidconnect.googleapis.com/v1/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    email = result.get("email")
    if not isinstance(email, str) or not email:
        raise GoogleServicesError(
            "Google did not return an authenticated email."
        )
    return email


def revoke_refresh_token(refresh_token):
    if not refresh_token:
        return
    _request(
        "https://oauth2.googleapis.com/revoke",
        urllib.parse.urlencode({"token": refresh_token}).encode(),
        {"Content-Type": "application/x-www-form-urlencoded"},
    )