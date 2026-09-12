from unittest.mock import patch

from cryptography.fernet import Fernet
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from core.google_services import (
    GoogleServicesError,
    decrypt_refresh_token,
    encrypt_refresh_token,
)
from core.models import GoogleServicesIntegration


GOOGLE_SETTINGS = {
    "GOOGLE_SERVICES_OAUTH_CLIENT_ID": "client-id",
    "GOOGLE_SERVICES_OAUTH_CLIENT_SECRET": "client-secret",
    "GOOGLE_SERVICES_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "GOOGLE_SERVICES_CALLBACK_URI": (
        "https://example.com/integrations/google/callback/"
    ),
}
GRANTED_SCOPES = (
    "openid email "
    "https://www.googleapis.com/auth/analytics.edit "
    "https://www.googleapis.com/auth/webmasters "
    "https://www.googleapis.com/auth/siteverification"
)


@override_settings(**GOOGLE_SETTINGS)
class GoogleServicesTests(TestCase):
    def setUp(self):
        self.superuser = get_user_model().objects.create_superuser(
            username="google-admin",
            email="admin@example.com",
            password="a-long-password-123",
        )
        self.staff = get_user_model().objects.create_user(
            username="staff",
            email="staff@example.com",
            password="a-long-password-123",
            is_staff=True,
        )
        self.client.force_login(self.superuser)

    def test_dashboard_requires_superuser_and_is_not_cached(self):
        self.client.force_login(self.staff)
        self.assertEqual(
            self.client.get(reverse("google-services-dashboard")).status_code,
            403,
        )
        self.client.force_login(self.superuser)
        response = self.client.get(reverse("google-services-dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("no-cache", response["Cache-Control"])
        self.assertContains(
            response,
            "https://example.com/integrations/google/callback/",
        )

    def test_inactive_superuser_is_forbidden(self):
        self.superuser.is_active = False
        self.superuser.save(update_fields=["is_active"])

        response = self.client.get(reverse("google-services-dashboard"))

        self.assertEqual(response.status_code, 302)

    def test_connect_is_post_only_and_uses_pkce_and_state(self):
        self.assertEqual(
            self.client.get(reverse("google-services-connect")).status_code,
            405,
        )
        response = self.client.post(reverse("google-services-connect"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com/o/oauth2/v2/auth", response.url)
        self.assertIn("code_challenge=", response.url)
        self.assertIn("access_type=offline", response.url)
        self.assertIn("google_services_oauth", self.client.session)

    @override_settings(GOOGLE_SERVICES_OAUTH_CLIENT_ID="")
    def test_connect_is_disabled_until_settings_are_complete(self):
        response = self.client.post(reverse("google-services-connect"))
        self.assertEqual(response.status_code, 503)

    @override_settings(GOOGLE_SERVICES_ENCRYPTION_KEY="invalid")
    def test_connect_rejects_invalid_encryption_key(self):
        self.assertEqual(
            self.client.post(reverse("google-services-connect")).status_code,
            503,
        )

    @override_settings(
        GOOGLE_SERVICES_CALLBACK_URI=(
            "http://example.com/integrations/google/callback/"
        )
    )
    def test_connect_rejects_insecure_callback(self):
        self.assertEqual(
            self.client.post(reverse("google-services-connect")).status_code,
            503,
        )

    def test_refresh_token_is_encrypted_and_invalid_key_fails(self):
        encrypted = encrypt_refresh_token("refresh-secret")
        self.assertNotIn("refresh-secret", encrypted)
        self.assertEqual(decrypt_refresh_token(encrypted), "refresh-secret")
        with override_settings(GOOGLE_SERVICES_ENCRYPTION_KEY="invalid"):
            with self.assertRaises(GoogleServicesError):
                decrypt_refresh_token(encrypted)

    @patch("core.google_views.authenticated_email", return_value="owner@example.com")
    @patch("core.google_views.exchange_code")
    def test_callback_validates_state_and_encrypts_refresh_token(
        self,
        exchange_code,
        _authenticated_email,
    ):
        session = self.client.session
        session["google_services_oauth"] = {
            "state": "expected-state",
            "verifier": "pkce-verifier",
        }
        session.save()
        exchange_code.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-secret",
            "scope": GRANTED_SCOPES,
        }

        response = self.client.get(
            reverse("google-services-callback"),
            {"state": "expected-state", "code": "authorization-code"},
        )

        self.assertRedirects(
            response,
            reverse("google-services-dashboard"),
        )
        record = GoogleServicesIntegration.objects.get()
        self.assertEqual(record.connected_email, "owner@example.com")
        self.assertEqual(
            decrypt_refresh_token(record.refresh_token_encrypted),
            "refresh-secret",
        )
        self.assertNotIn("google_services_oauth", self.client.session)

    @patch("core.google_views.exchange_code")
    def test_callback_rejects_invalid_state_before_exchange(self, exchange_code):
        response = self.client.get(
            reverse("google-services-callback"),
            {"state": "attacker-state", "code": "authorization-code"},
        )

        self.assertEqual(response.status_code, 400)
        exchange_code.assert_not_called()

    @patch("core.google_views.authenticated_email", return_value="owner@example.com")
    @patch(
        "core.google_views.exchange_code",
        return_value={
            "access_token": "access-token",
            "scope": GRANTED_SCOPES,
        },
    )
    def test_first_connection_requires_refresh_token(
        self,
        _exchange_code,
        _authenticated_email,
    ):
        session = self.client.session
        session["google_services_oauth"] = {
            "state": "expected-state",
            "verifier": "pkce-verifier",
        }
        session.save()

        response = self.client.get(
            reverse("google-services-callback"),
            {"state": "expected-state", "code": "authorization-code"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(GoogleServicesIntegration.objects.exists())

    @patch("core.google_views.authenticated_email")
    @patch("core.google_views.exchange_code")
    def test_callback_rejects_partial_scope_grant(
        self,
        exchange_code,
        authenticated_email,
    ):
        session = self.client.session
        session["google_services_oauth"] = {
            "state": "expected-state",
            "verifier": "pkce-verifier",
        }
        session.save()
        exchange_code.return_value = {
            "access_token": "access-token",
            "refresh_token": "refresh-secret",
            "scope": "openid email",
        }

        response = self.client.get(
            reverse("google-services-callback"),
            {"state": "expected-state", "code": "authorization-code"},
        )

        self.assertEqual(response.status_code, 400)
        authenticated_email.assert_not_called()
        self.assertFalse(GoogleServicesIntegration.objects.exists())

    def test_reconnect_is_blocked_until_disconnect(self):
        GoogleServicesIntegration.objects.create(
            connected_email="owner@example.com",
            refresh_token_encrypted=encrypt_refresh_token("refresh-secret"),
        )

        response = self.client.post(reverse("google-services-connect"))

        self.assertEqual(response.status_code, 409)
        self.assertNotIn("google_services_oauth", self.client.session)

    @patch("core.google_views.revoke_refresh_token")
    def test_disconnect_revokes_token_and_removes_connection(self, revoke):
        GoogleServicesIntegration.objects.create(
            connected_email="owner@example.com",
            refresh_token_encrypted=encrypt_refresh_token("refresh-secret"),
        )

        response = self.client.post(reverse("google-services-disconnect"))

        self.assertRedirects(
            response,
            reverse("google-services-dashboard"),
        )
        revoke.assert_called_once_with("refresh-secret")
        self.assertFalse(GoogleServicesIntegration.objects.exists())

    @patch(
        "core.google_views.revoke_refresh_token",
        side_effect=GoogleServicesError("network error"),
    )
    def test_failed_revocation_preserves_connection_for_retry(self, _revoke):
        record = GoogleServicesIntegration.objects.create(
            connected_email="owner@example.com",
            refresh_token_encrypted=encrypt_refresh_token("refresh-secret"),
        )

        response = self.client.post(reverse("google-services-disconnect"))

        self.assertEqual(response.status_code, 502)
        self.assertTrue(
            GoogleServicesIntegration.objects.filter(pk=record.pk).exists()
        )