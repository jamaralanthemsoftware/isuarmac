import http.client
import json
import socket
import time
from dataclasses import dataclass


POSTMARK_HOST = "api.postmarkapp.com"
POSTMARK_EMAIL_PATH = "/email"
CONNECT_TIMEOUT_SECONDS = 3
READ_TIMEOUT_SECONDS = 7
TOTAL_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 32_768
MAX_PAYLOAD_BYTES = 64_000
MAX_MESSAGE_CHARS = 10_000
MAX_RECIPIENTS = 20


class PostmarkDeliveryError(Exception):
    pass


@dataclass(frozen=True)
class PostmarkConfig:
    server_api_token: str
    from_email: str
    recipient_emails: tuple[str, ...]
    message_stream: str


def get_postmark_config():
    from .models import PostmarkIntegration

    integration = PostmarkIntegration.objects.filter(
        singleton_key="default",
        is_enabled=True,
    ).first()
    if not integration:
        return None
    return PostmarkConfig(
        server_api_token=integration.get_server_api_token(),
        from_email=integration.from_email,
        recipient_emails=tuple(integration.normalized_recipient_emails),
        message_stream=integration.message_stream,
    )


def _validate_config(config):
    return (
        isinstance(config.server_api_token, str)
        and bool(config.server_api_token.strip())
        and len(config.server_api_token) <= 512
        and isinstance(config.from_email, str)
        and bool(config.from_email.strip())
        and len(config.from_email) <= 254
        and isinstance(config.recipient_emails, tuple)
        and bool(config.recipient_emails)
        and len(config.recipient_emails) <= MAX_RECIPIENTS
        and all(
            isinstance(email, str)
            and bool(email.strip())
            and len(email) <= 254
            for email in config.recipient_emails
        )
        and isinstance(config.message_stream, str)
        and bool(config.message_stream.strip())
        and len(config.message_stream) <= 100
    )


def _remaining_timeout(deadline):
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise TimeoutError
    return min(READ_TIMEOUT_SECONDS, remaining)


def _read_bounded_response(response, connection, deadline):
    chunks = []
    total_bytes = 0
    while True:
        connection.sock.settimeout(_remaining_timeout(deadline))
        chunk = response.read1(
            min(8192, MAX_RESPONSE_BYTES + 1 - total_bytes)
        )
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)
        total_bytes += len(chunk)
        if total_bytes > MAX_RESPONSE_BYTES:
            raise PostmarkDeliveryError("Postmark returned an oversized response.")


def send_contact_lead_notification(lead, config=None):
    config = config or get_postmark_config()
    if config is None:
        return False
    if not _validate_config(config):
        raise PostmarkDeliveryError("Postmark is enabled but incomplete.")

    lead_fields = (
        lead.first_name,
        lead.last_name,
        lead.email,
        lead.phone,
        lead.source,
        lead.message,
    )
    if (
        any(not isinstance(value, str) for value in lead_fields)
        or len(lead.first_name) > 60
        or len(lead.last_name) > 60
        or len(lead.email) > 254
        or len(lead.phone) > 40
        or len(lead.source) > 120
        or len(lead.message) > MAX_MESSAGE_CHARS
    ):
        raise PostmarkDeliveryError("The form submission exceeds delivery limits.")
    full_name = f"{lead.first_name} {lead.last_name}".strip()

    try:
        payload = json.dumps(
            {
                "From": config.from_email,
                "To": ",".join(config.recipient_emails),
                "ReplyTo": lead.email,
                "Subject": (
                    f"New website form submission from {full_name}"
                ),
                "TextBody": (
                    f"First name: {lead.first_name}\n"
                    f"Last name: {lead.last_name}\n"
                    f"Email: {lead.email}\n"
                    f"Phone: {lead.phone or 'Not provided'}\n"
                    f"Source: {lead.source or 'website'}\n\n"
                    f"Message:\n{lead.message}"
                ),
                "MessageStream": config.message_stream,
                "Tag": "contact-form",
            }
        ).encode()
    except (TypeError, ValueError, UnicodeEncodeError) as error:
        raise PostmarkDeliveryError(
            "The form submission could not be prepared for delivery."
        ) from error
    if len(payload) > MAX_PAYLOAD_BYTES:
        raise PostmarkDeliveryError("The Postmark request is too large.")

    deadline = time.monotonic() + TOTAL_TIMEOUT_SECONDS
    connection = http.client.HTTPSConnection(
        POSTMARK_HOST,
        443,
        timeout=CONNECT_TIMEOUT_SECONDS,
    )
    try:
        connection.connect()
        connection.sock.settimeout(_remaining_timeout(deadline))
        connection.request(
            "POST",
            POSTMARK_EMAIL_PATH,
            body=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-Postmark-Server-Token": config.server_api_token,
            },
        )
        connection.sock.settimeout(_remaining_timeout(deadline))
        response = connection.getresponse()
        response_body = _read_bounded_response(
            response,
            connection,
            deadline,
        )
        if response.status != 200:
            raise PostmarkDeliveryError(
                f"Postmark returned HTTP {response.status}."
            )
        result = json.loads(response_body)
        if (
            not isinstance(result, dict)
            or result.get("ErrorCode") != 0
            or not isinstance(result.get("MessageID"), str)
            or not result["MessageID"]
        ):
            raise PostmarkDeliveryError("Postmark returned an invalid response.")
        return True
    except PostmarkDeliveryError:
        raise
    except (
        OSError,
        TimeoutError,
        socket.timeout,
        http.client.HTTPException,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as error:
        raise PostmarkDeliveryError("Postmark delivery failed.") from error
    finally:
        connection.close()