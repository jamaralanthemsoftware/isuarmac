import json
import socket
from concurrent.futures import TimeoutError as FutureTimeoutError
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.admin import AnthemCRMIntegrationAdminForm
from core.anthem import deliver_lead_to_anthem
from core.models import (
    AnthemCRMIntegration,
    Lead,
    validate_anthem_webhook_url,
)


VALID_WEBHOOK = (
    "https://live.anthemcrm.com/api/v1/organization/123/"
    "gravity-forms-webhook/"
)


@override_settings(SECRET_KEY="test-secret-key-for-anthem")
class AnthemDeliveryTests(TestCase):
    def make_lead(self):
        return Lead.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="3145550123",
            source="website",
            message="Please contact me about an estimate.",
            consent_to_contact=True,
        )

    def enable_integration(self):
        integration = AnthemCRMIntegration.objects.create(is_enabled=True)
        integration.set_webhook_url(VALID_WEBHOOK)
        integration.save()
        return integration

    def test_contact_form_uses_separate_required_name_fields(self):
        response = self.client.get(reverse("contact"))

        self.assertContains(response, 'name="first_name"')
        self.assertContains(response, 'name="last_name"')
        self.assertNotContains(response, 'name="name"')
        self.assertTrue(response.context["form"].fields["first_name"].required)
        self.assertTrue(response.context["form"].fields["last_name"].required)

    def mocked_response(self, connection_class, *, status, payload):
        connection = connection_class.return_value
        connection.sock = connection
        response = connection.getresponse.return_value
        response.status = status
        response.read.return_value = json.dumps(payload).encode()
        return connection

    def test_integration_is_disabled_and_webhook_is_encrypted(self):
        integration = AnthemCRMIntegration.objects.create()
        self.assertFalse(integration.is_enabled)

        integration.set_webhook_url(VALID_WEBHOOK)
        integration.save()

        self.assertNotIn(VALID_WEBHOOK, integration.webhook_url_encrypted)
        self.assertEqual(integration.get_webhook_url(), VALID_WEBHOOK)

    def test_admin_rejects_wrong_host_and_requires_url_before_enabling(self):
        wrong_host = AnthemCRMIntegrationAdminForm(
            data={
                "webhook_url": (
                    "https://attacker.example/api/v1/organization/123/"
                    "gravity-forms-webhook/"
                ),
                "is_enabled": "on",
            }
        )
        self.assertFalse(wrong_host.is_valid())
        self.assertIn("webhook_url", wrong_host.errors)

        missing_url = AnthemCRMIntegrationAdminForm(
            data={"webhook_url": "", "is_enabled": "on"}
        )
        self.assertFalse(missing_url.is_valid())
        self.assertIn("webhook_url", missing_url.errors)

    def test_webhook_url_rejects_unsafe_variants(self):
        unsafe_urls = (
            (
                "https://user:password@live.anthemcrm.com/api/v1/"
                "organization/123/gravity-forms-webhook/"
            ),
            (
                "https://live.anthemcrm.com:444/api/v1/organization/123/"
                "gravity-forms-webhook/"
            ),
            (
                "https://live.anthemcrm.com/api/v1/organization/123/"
                "gravity-forms-webhook/?token=value"
            ),
            (
                "https://live.anthemcrm.com/api/v1/organization/123/"
                "gravity-forms-webhook/#fragment"
            ),
            (
                "https://live.anthemcrm.com/api/v1/organization/123/"
                "different-endpoint/"
            ),
        )

        for url in unsafe_urls:
            with self.subTest(url=url), self.assertRaises(ValidationError):
                validate_anthem_webhook_url(url)

    @patch("core.anthem.http.client.HTTPSConnection")
    def test_disabled_integration_never_contacts_crm(self, connection_class):
        lead = self.make_lead()

        self.assertIsNone(deliver_lead_to_anthem(lead.pk))

        lead.refresh_from_db()
        self.assertEqual(
            lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.NOT_SENT,
        )
        connection_class.assert_not_called()

    @patch("core.anthem.http.client.HTTPSConnection")
    def test_confirmed_delivery_sends_native_django_form_payload(
        self, connection_class
    ):
        self.enable_integration()
        lead = self.make_lead()
        connection = self.mocked_response(
            connection_class,
            status=201,
            payload={
                "success": True,
                "results": {"prospect_id": 987},
            },
        )

        self.assertTrue(deliver_lead_to_anthem(lead.pk))

        lead.refresh_from_db()
        self.assertEqual(
            lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.CONFIRMED,
        )
        self.assertEqual(lead.anthem_http_status, 201)
        self.assertEqual(lead.anthem_record_identifier, "987")
        _, path = connection.request.call_args.args[:2]
        payload = json.loads(connection.request.call_args.kwargs["body"])
        self.assertEqual(
            path,
            "/api/v1/organization/123/gravity-forms-webhook/",
        )
        self.assertEqual(payload["first_name"], "Jane")
        self.assertEqual(payload["last_name"], "Smith")
        self.assertEqual(payload["email"], "jane@example.com")
        self.assertEqual(payload["cell_phone"], "3145550123")
        self.assertIn(
            "Message: Please contact me about an estimate.",
            payload["notes"],
        )

    @patch("core.anthem.http.client.HTTPSConnection")
    def test_unconfirmed_response_needs_review(self, connection_class):
        self.enable_integration()
        lead = self.make_lead()
        self.mocked_response(
            connection_class,
            status=200,
            payload={"success": False, "results": {}},
        )

        self.assertFalse(deliver_lead_to_anthem(lead.pk))

        lead.refresh_from_db()
        self.assertEqual(
            lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.NEEDS_REVIEW,
        )

    @patch("core.anthem.http.client.HTTPSConnection")
    def test_non_2xx_success_true_is_not_confirmed(self, connection_class):
        self.enable_integration()
        lead = self.make_lead()
        self.mocked_response(
            connection_class,
            status=500,
            payload={"success": True, "results": {"id": "uncertain"}},
        )

        self.assertFalse(deliver_lead_to_anthem(lead.pk))

        lead.refresh_from_db()
        self.assertEqual(
            lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.NEEDS_REVIEW,
        )

    @patch("core.anthem.http.client.HTTPSConnection")
    def test_connection_close_response_still_records_result(
        self, connection_class
    ):
        self.enable_integration()
        lead = self.make_lead()
        connection = self.mocked_response(
            connection_class,
            status=201,
            payload={"success": True, "results": {"id": "crm-id"}},
        )
        connection.getresponse.side_effect = (
            lambda: (
                setattr(connection, "sock", None)
                or connection.getresponse.return_value
            )
        )

        self.assertTrue(deliver_lead_to_anthem(lead.pk))

        lead.refresh_from_db()
        self.assertEqual(
            lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.CONFIRMED,
        )

    @patch("core.anthem.http.client.HTTPSConnection")
    def test_timeout_is_not_retried_automatically(self, connection_class):
        self.enable_integration()
        lead = self.make_lead()
        connection_class.return_value.connect.side_effect = socket.timeout()

        self.assertFalse(deliver_lead_to_anthem(lead.pk))
        self.assertFalse(deliver_lead_to_anthem(lead.pk))

        lead.refresh_from_db()
        self.assertEqual(
            lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.NEEDS_REVIEW,
        )
        self.assertEqual(connection_class.return_value.connect.call_count, 1)

    @patch("core.anthem._DELIVERY_EXECUTOR")
    def test_total_deadline_marks_delivery_for_review(self, executor):
        self.enable_integration()
        lead = self.make_lead()
        executor.submit.return_value.result.side_effect = FutureTimeoutError

        self.assertFalse(deliver_lead_to_anthem(lead.pk))

        lead.refresh_from_db()
        self.assertEqual(
            lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.NEEDS_REVIEW,
        )
        executor.submit.return_value.cancel.assert_called_once()

    @patch("core.anthem.http.client.HTTPSConnection")
    def test_malformed_and_oversized_responses_need_review(
        self, connection_class
    ):
        self.enable_integration()
        malformed_lead = self.make_lead()
        connection = connection_class.return_value
        connection.sock = connection
        response = connection.getresponse.return_value
        response.status = 201
        response.read.return_value = b"not-json"

        self.assertFalse(deliver_lead_to_anthem(malformed_lead.pk))

        malformed_lead.refresh_from_db()
        self.assertEqual(
            malformed_lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.NEEDS_REVIEW,
        )

        oversized_lead = self.make_lead()
        response.read.return_value = b"x" * 65_537
        self.assertFalse(deliver_lead_to_anthem(oversized_lead.pk))
        oversized_lead.refresh_from_db()
        self.assertEqual(
            oversized_lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.NEEDS_REVIEW,
        )

    @patch("core.anthem.http.client.HTTPSConnection")
    def test_already_claimed_delivery_is_not_sent_again(
        self, connection_class
    ):
        self.enable_integration()
        lead = self.make_lead()
        lead.anthem_delivery_status = Lead.AnthemDeliveryStatus.ATTEMPTING
        lead.save(update_fields=["anthem_delivery_status"])

        self.assertFalse(deliver_lead_to_anthem(lead.pk))
        connection_class.assert_not_called()

    @patch("core.anthem.http.client.HTTPSConnection")
    def test_corrupt_enabled_webhook_fails_before_network(
        self, connection_class
    ):
        integration = AnthemCRMIntegration.objects.create(
            webhook_url_encrypted="invalid-ciphertext",
            is_enabled=True,
        )
        lead = self.make_lead()

        self.assertFalse(deliver_lead_to_anthem(lead.pk))

        lead.refresh_from_db()
        self.assertEqual(
            lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.CONFIGURATION_ERROR,
        )
        self.assertFalse(integration.webhook_url_configured)

        confirmed_lead = self.make_lead()
        confirmed_lead.anthem_delivery_status = (
            Lead.AnthemDeliveryStatus.CONFIRMED
        )
        confirmed_lead.save(update_fields=["anthem_delivery_status"])
        self.assertFalse(deliver_lead_to_anthem(confirmed_lead.pk))
        confirmed_lead.refresh_from_db()
        self.assertEqual(
            confirmed_lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.CONFIRMED,
        )
        connection_class.assert_not_called()

    @patch("core.anthem.http.client.HTTPSConnection")
    def test_contact_submission_delivers_to_crm(self, connection_class):
        self.enable_integration()
        self.mocked_response(
            connection_class,
            status=201,
            payload={"success": True, "results": {"id": "crm-id"}},
        )

        response = self.client.post(
            reverse("contact"),
            {
                "first_name": "Contact",
                "last_name": "Visitor",
                "email": "visitor@example.com",
                "phone": "555-0100",
                "message": "Please call me.",
                "consent_to_contact": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get(email="visitor@example.com")
        self.assertEqual(
            lead.anthem_delivery_status,
            Lead.AnthemDeliveryStatus.CONFIRMED,
        )

    @patch("core.views.deliver_lead_to_anthem", return_value=False)
    def test_contact_submission_is_saved_when_crm_delivery_fails(self, _deliver):
        response = self.client.post(
            reverse("contact"),
            {
                "first_name": "Saved",
                "last_name": "Visitor",
                "email": "saved@example.com",
                "message": "Please save this even if CRM delivery fails.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Lead.objects.filter(email="saved@example.com").exists())
        messages = [
            str(message)
            for message in get_messages(response.wsgi_request)
        ]
        self.assertTrue(
            any("could not sync it to our customer system" in message for message in messages)
        )