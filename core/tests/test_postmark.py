import json
import socket
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.models import Lead, PostmarkIntegration
from core.admin import PostmarkIntegrationAdminForm
from core.postmark import (
    MAX_MESSAGE_CHARS,
    PostmarkConfig,
    PostmarkDeliveryError,
    send_contact_lead_notification,
)


CONFIG = PostmarkConfig(
    server_api_token="server-token",
    from_email="forms@example.com",
    recipient_emails=("owner@example.com", "office@example.com"),
    message_stream="outbound",
)


class LeadStub:
    first_name = "Website"
    last_name = "Visitor"
    email = "visitor@example.com"
    phone = "555-0100"
    source = "website contact"
    message = "Please contact me."


class PostmarkDeliveryTests(SimpleTestCase):
    def mocked_response(self, connection_class, payload, status=200):
        connection = connection_class.return_value
        connection.sock = connection
        response = connection.getresponse.return_value
        response.status = status
        response.read1.side_effect = [json.dumps(payload).encode(), b""]
        return connection

    @patch("core.postmark.http.client.HTTPSConnection")
    def test_delivery_uses_postmark_api_and_expected_addresses(
        self, connection_class
    ):
        connection = self.mocked_response(
            connection_class,
            {"ErrorCode": 0, "MessageID": "message-id"},
        )

        self.assertTrue(send_contact_lead_notification(LeadStub(), CONFIG))

        _, path = connection.request.call_args.args[:2]
        self.assertEqual(path, "/email")
        request = connection.request.call_args
        headers = request.kwargs["headers"]
        body = json.loads(request.kwargs["body"])
        self.assertEqual(headers["X-Postmark-Server-Token"], "server-token")
        self.assertEqual(body["From"], "forms@example.com")
        self.assertEqual(
            body["To"],
            "owner@example.com,office@example.com",
        )
        self.assertEqual(body["ReplyTo"], "visitor@example.com")

    @patch("core.postmark.http.client.HTTPSConnection")
    def test_invalid_response_and_timeout_raise_delivery_error(
        self, connection_class
    ):
        self.mocked_response(connection_class, {"ErrorCode": 10}, status=422)
        with self.assertRaises(PostmarkDeliveryError):
            send_contact_lead_notification(LeadStub(), CONFIG)

        connection_class.return_value.connect.side_effect = socket.timeout()
        with self.assertRaises(PostmarkDeliveryError):
            send_contact_lead_notification(LeadStub(), CONFIG)

    @patch("core.postmark.http.client.HTTPSConnection")
    def test_oversized_submission_fails_before_network(self, connection_class):
        lead = LeadStub()
        lead.message = "x" * (MAX_MESSAGE_CHARS + 1)

        with self.assertRaises(PostmarkDeliveryError):
            send_contact_lead_notification(lead, CONFIG)
        connection_class.assert_not_called()

    @patch("core.postmark.http.client.HTTPSConnection")
    def test_oversized_and_malformed_responses_fail_closed(
        self, connection_class
    ):
        connection = connection_class.return_value
        connection.sock = connection
        response = connection.getresponse.return_value
        response.status = 200
        response.read1.side_effect = [b"x" * 32769]
        with self.assertRaises(PostmarkDeliveryError):
            send_contact_lead_notification(LeadStub(), CONFIG)

        response.read1.side_effect = [b"not-json", b""]
        with self.assertRaises(PostmarkDeliveryError):
            send_contact_lead_notification(LeadStub(), CONFIG)

    @patch("core.postmark.time.monotonic", side_effect=[0, 11])
    @patch("core.postmark.http.client.HTTPSConnection")
    def test_total_delivery_deadline_is_enforced(
        self, connection_class, _monotonic
    ):
        connection_class.return_value.sock = connection_class.return_value

        with self.assertRaises(PostmarkDeliveryError):
            send_contact_lead_notification(LeadStub(), CONFIG)

    @patch("core.postmark.http.client.HTTPSConnection")
    def test_incomplete_enabled_config_fails_before_network(
        self, connection_class
    ):
        invalid_config = PostmarkConfig(
            server_api_token="",
            from_email="forms@example.com",
            recipient_emails=("owner@example.com",),
            message_stream="outbound",
        )

        with self.assertRaises(PostmarkDeliveryError):
            send_contact_lead_notification(LeadStub(), invalid_config)
        connection_class.assert_not_called()


@override_settings(SECRET_KEY="test-secret-key-for-encryption")
class PostmarkIntegrationTests(TestCase):
    def test_defaults_are_disabled_and_token_is_encrypted(self):
        integration = PostmarkIntegration.objects.create()
        self.assertFalse(integration.is_enabled)

        integration.set_server_api_token("postmark-secret-token")
        integration.save()

        self.assertNotIn(
            "postmark-secret-token",
            integration.server_api_token_encrypted,
        )
        self.assertEqual(
            integration.get_server_api_token(),
            "postmark-secret-token",
        )

    def test_corrupt_token_is_not_reported_as_configured(self):
        integration = PostmarkIntegration.objects.create(
            server_api_token_encrypted="not-valid-ciphertext"
        )

        self.assertFalse(integration.server_api_token_configured)

    def test_admin_requires_decryptable_token_before_enabling(self):
        integration = PostmarkIntegration.objects.create(
            server_api_token_encrypted="not-valid-ciphertext"
        )
        form = PostmarkIntegrationAdminForm(
            instance=integration,
            data={
                "from_email": "forms@example.com",
                "recipient_emails": "owner@example.com",
                "message_stream": "outbound",
                "server_api_token": "",
                "is_enabled": "on",
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn("server_api_token", form.errors)

    @patch("core.postmark.http.client.HTTPSConnection")
    def test_disabled_postmark_saves_lead_without_network(
        self, connection_class
    ):
        response = self.client.post(
            reverse("contact"),
            {
                "first_name": "Saved",
                "last_name": "Visitor",
                "email": "saved@example.com",
                "message": "Please save this submission.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(Lead.objects.filter(email="saved@example.com").exists())
        connection_class.assert_not_called()

    @patch(
        "core.views.send_contact_lead_notification",
        side_effect=PostmarkDeliveryError,
    )
    def test_delivery_failure_preserves_lead_and_warns_user(self, _send):
        response = self.client.post(
            reverse("contact"),
            {
                "first_name": "Saved",
                "last_name": "Visitor",
                "email": "saved@example.com",
                "message": "Please save this submission.",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(Lead.objects.filter(email="saved@example.com").exists())
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        self.assertTrue(
            any("saved, but we could not alert our team" in message for message in messages)
        )

    @patch("core.postmark.http.client.HTTPSConnection")
    def test_enabled_contact_form_sends_notification(
        self, connection_class
    ):
        integration = PostmarkIntegration.objects.create(
            from_email="forms@example.com",
            recipient_emails="owner@example.com",
            message_stream="outbound",
            is_enabled=True,
        )
        integration.set_server_api_token("server-token")
        integration.save()
        connection = connection_class.return_value
        connection.sock = connection
        response = connection.getresponse.return_value
        response.status = 200
        response.read1.side_effect = [
            json.dumps(
                {"ErrorCode": 0, "MessageID": "message-id"}
            ).encode(),
            b"",
        ]

        response = self.client.post(
            reverse("contact"),
            {
                "first_name": "Notified",
                "last_name": "Visitor",
                "email": "notified@example.com",
                "message": "Please email the team.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(
            Lead.objects.filter(email="notified@example.com").exists()
        )
        connection.request.assert_called_once()