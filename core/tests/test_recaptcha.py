import json
import socket
from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError, transaction
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.models import Lead, RecaptchaIntegration
from core.recaptcha import RecaptchaConfig, verify_contact_recaptcha


CONFIG = RecaptchaConfig(
    site_key="test-site-key",
    secret_key="test-secret",
    minimum_score=0.80,
    allowed_hostnames=frozenset({"example.com", "www.example.com"}),
)


class RecaptchaVerificationTests(SimpleTestCase):
    def mocked_response(self, connection_class, payload, status=200):
        connection = connection_class.return_value
        connection.sock = connection
        response = connection.getresponse.return_value
        response.status = status
        response.read.return_value = json.dumps(payload).encode()
        return connection

    @patch("core.recaptcha.http.client.HTTPSConnection")
    def test_score_at_default_threshold_is_accepted(self, connection_class):
        self.mocked_response(
            connection_class,
            {
                "success": True,
                "score": 0.80,
                "action": "contact_form",
                "hostname": "example.com",
            },
        )

        self.assertTrue(verify_contact_recaptcha("browser-token", CONFIG))

    @patch("core.recaptcha.http.client.HTTPSConnection")
    def test_score_below_default_threshold_is_rejected(self, connection_class):
        self.mocked_response(
            connection_class,
            {
                "success": True,
                "score": 0.79,
                "action": "contact_form",
                "hostname": "example.com",
            },
        )

        self.assertFalse(verify_contact_recaptcha("browser-token", CONFIG))

    @patch("core.recaptcha.http.client.HTTPSConnection")
    def test_wrong_action_hostname_and_timeout_fail_closed(self, connection_class):
        for action, hostname in (
            ("login", "example.com"),
            ("contact_form", "attacker.example"),
        ):
            with self.subTest(action=action, hostname=hostname):
                self.mocked_response(
                    connection_class,
                    {
                        "success": True,
                        "score": 0.99,
                        "action": action,
                        "hostname": hostname,
                    },
                )
                self.assertFalse(
                    verify_contact_recaptcha("browser-token", CONFIG)
                )

        connection_class.return_value.connect.side_effect = socket.timeout()
        self.assertFalse(verify_contact_recaptcha("browser-token", CONFIG))

    @patch("core.recaptcha.http.client.HTTPSConnection")
    def test_malformed_provider_fields_fail_closed(self, connection_class):
        for score, action, hostname in (
            (True, "contact_form", "example.com"),
            ("0.99", "contact_form", "example.com"),
            (0.99, ["contact_form"], "example.com"),
            (0.99, "contact_form", ["example.com"]),
        ):
            with self.subTest(score=score, action=action, hostname=hostname):
                self.mocked_response(
                    connection_class,
                    {
                        "success": True,
                        "score": score,
                        "action": action,
                        "hostname": hostname,
                    },
                )
                self.assertFalse(
                    verify_contact_recaptcha("browser-token", CONFIG)
                )

    @patch("core.recaptcha.http.client.HTTPSConnection")
    def test_invalid_enabled_configuration_fails_before_network(
        self, connection_class
    ):
        invalid_configs = (
            RecaptchaConfig("", "secret", 0.80, frozenset({"example.com"})),
            RecaptchaConfig("site", "", 0.80, frozenset({"example.com"})),
            RecaptchaConfig("site", "secret", 0.80, frozenset()),
            RecaptchaConfig("site", "secret", -1, frozenset({"example.com"})),
            RecaptchaConfig(
                "site",
                "secret",
                float("nan"),
                frozenset({"example.com"}),
            ),
        )

        for config in invalid_configs:
            with self.subTest(config=config):
                self.assertFalse(
                    verify_contact_recaptcha("browser-token", config)
                )
        connection_class.assert_not_called()

    @patch("core.recaptcha.http.client.HTTPSConnection")
    def test_http_and_malformed_json_responses_fail_closed(self, connection_class):
        self.mocked_response(connection_class, {}, status=500)
        self.assertFalse(verify_contact_recaptcha("browser-token", CONFIG))

        connection = connection_class.return_value
        connection.getresponse.return_value.status = 200
        connection.getresponse.return_value.read.return_value = b"not-json"
        self.assertFalse(verify_contact_recaptcha("browser-token", CONFIG))

    @patch("core.recaptcha.http.client.HTTPSConnection")
    def test_disabled_integration_never_contacts_google(self, connection_class):
        self.assertTrue(verify_contact_recaptcha("", None))
        connection_class.assert_not_called()


@override_settings(SECRET_KEY="test-secret-key-for-encryption")
class RecaptchaIntegrationTests(TestCase):
    def test_defaults_are_safe_for_a_template(self):
        integration = RecaptchaIntegration()

        self.assertEqual(integration.minimum_score, Decimal("0.80"))
        self.assertFalse(integration.is_enabled)
        self.assertFalse(integration.secret_key_configured)

    def test_secret_key_is_encrypted_and_can_be_decrypted(self):
        integration = RecaptchaIntegration.objects.create()
        integration.set_secret_key("google-secret-value")
        integration.save()

        self.assertNotIn("google-secret-value", integration.secret_key_encrypted)
        self.assertEqual(integration.get_secret_key(), "google-secret-value")
        self.assertTrue(integration.secret_key_configured)

        integration.secret_key_encrypted = "invalid-ciphertext"
        self.assertFalse(integration.secret_key_configured)

    def test_database_rejects_threshold_outside_zero_and_one(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            RecaptchaIntegration.objects.create(minimum_score=Decimal("1.01"))

    def test_enabled_contact_form_loads_invisible_recaptcha(self):
        integration = RecaptchaIntegration.objects.create(
            site_key="public-site-key",
            allowed_hostnames="example.com",
            is_enabled=True,
        )
        integration.set_secret_key("google-secret-value")
        integration.save()

        response = self.client.get(reverse("contact"))

        self.assertContains(
            response,
            'data-recaptcha-site-key="public-site-key"',
        )
        self.assertContains(response, 'name="recaptcha_token"')
        self.assertContains(
            response,
            "https://www.google.com/recaptcha/api.js?render=public-site-key",
        )
        self.assertNotContains(response, "google-secret-value")

    @patch("core.views.verify_contact_recaptcha", return_value=False)
    def test_failed_verification_does_not_save_lead(self, _verify):
        integration = RecaptchaIntegration.objects.create(
            site_key="public-site-key",
            allowed_hostnames="example.com",
            is_enabled=True,
        )
        integration.set_secret_key("google-secret-value")
        integration.save()

        response = self.client.post(
            reverse("contact"),
            {
                "first_name": "Blocked",
                "last_name": "Submission",
                "email": "blocked@example.com",
                "message": "This should not be saved.",
                "recaptcha_token": "invalid-token",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Lead.objects.exists())

    @patch("core.recaptcha.http.client.HTTPSConnection")
    def test_disabled_contact_form_saves_without_contacting_google(
        self, connection_class
    ):
        response = self.client.post(
            reverse("contact"),
            {
                "first_name": "Allowed",
                "last_name": "Submission",
                "email": "allowed@example.com",
                "message": "This should be saved while reCAPTCHA is disabled.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Lead.objects.filter(email="allowed@example.com").exists())
        connection_class.assert_not_called()