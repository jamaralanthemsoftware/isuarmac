import http.client
import json
import socket
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from urllib.parse import urlsplit

from django.db import transaction
from django.utils import timezone

from .models import AnthemCRMIntegration, Lead, validate_anthem_webhook_url


CONNECT_TIMEOUT_SECONDS = 3
READ_TIMEOUT_SECONDS = 7
TOTAL_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BYTES = 65_536
MAX_PAYLOAD_BYTES = 65_536
_DELIVERY_EXECUTOR = ThreadPoolExecutor(
    max_workers=4,
    thread_name_prefix="anthem-webhook",
)


class AnthemConfigurationError(ValueError):
    pass


def _validated_destination():
    integration = AnthemCRMIntegration.objects.filter(
        singleton_key="default",
        is_enabled=True,
    ).first()
    if integration is None:
        return None
    webhook_url = integration.get_webhook_url()
    if not webhook_url:
        raise AnthemConfigurationError(
            "The enabled Anthem CRM webhook cannot be decrypted."
        )
    try:
        validate_anthem_webhook_url(webhook_url)
    except Exception:
        raise AnthemConfigurationError(
            "The enabled Anthem CRM webhook is invalid."
        ) from None
    return urlsplit(webhook_url)


def _claim_delivery(lead_id):
    with transaction.atomic():
        lead = Lead.objects.select_for_update().get(pk=lead_id)
        if (
            lead.anthem_delivery_status
            != Lead.AnthemDeliveryStatus.NOT_SENT
        ):
            return None
        lead.anthem_delivery_status = Lead.AnthemDeliveryStatus.ATTEMPTING
        lead.anthem_attempted_at = timezone.now()
        lead.save(
            update_fields=[
                "anthem_delivery_status",
                "anthem_attempted_at",
                "updated_at",
            ]
        )
        return lead


def _record_result(
    lead_id,
    *,
    status,
    http_status=None,
    error_summary="",
    record_identifier="",
):
    Lead.objects.filter(pk=lead_id).update(
        anthem_delivery_status=status,
        anthem_http_status=http_status,
        anthem_error_summary=error_summary[:240],
        anthem_record_identifier=record_identifier[:120],
        updated_at=timezone.now(),
    )


def _extract_record_identifier(response_data):
    results = response_data.get("results")
    if not isinstance(results, dict):
        return ""
    for key in ("id", "prospect_id", "prospectId", "record_id", "recordId"):
        value = results.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            return str(value)
    return ""


def _payload_for_lead(lead):
    payload = {
        "first_name": lead.first_name,
        "last_name": lead.last_name,
        "email": lead.email,
        "cell_phone": lead.phone,
        "notes": (
            f"Source: {lead.source or 'website'}\n"
            f"Consent to contact: {'Yes' if lead.consent_to_contact else 'No'}\n"
            f"Message: {lead.message}"
        ),
    }
    encoded = json.dumps(payload).encode("utf-8")
    if len(encoded) > MAX_PAYLOAD_BYTES:
        raise ValueError("The Anthem CRM payload is too large.")
    return encoded


def _perform_webhook_request(destination, payload):
    connection = http.client.HTTPSConnection(
        destination.hostname,
        destination.port or 443,
        timeout=CONNECT_TIMEOUT_SECONDS,
    )
    try:
        connection.connect()
        connection.sock.settimeout(READ_TIMEOUT_SECONDS)
        connection.request(
            "POST",
            destination.path,
            body=payload,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        response = connection.getresponse()
        response_body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(response_body) > MAX_RESPONSE_BYTES:
            raise ValueError("Anthem returned an oversized response.")
        return response.status, response_body
    finally:
        connection.close()


def deliver_lead_to_anthem(lead_id):
    try:
        destination = _validated_destination()
    except AnthemConfigurationError as error:
        _record_result(
            lead_id,
            status=Lead.AnthemDeliveryStatus.CONFIGURATION_ERROR,
            error_summary=str(error),
        )
        return False
    if destination is None:
        return None

    lead = _claim_delivery(lead_id)
    if lead is None:
        return False

    response_status = None
    try:
        payload = _payload_for_lead(lead)
        future = _DELIVERY_EXECUTOR.submit(
            _perform_webhook_request,
            destination,
            payload,
        )
        response_status, response_body = future.result(
            timeout=TOTAL_TIMEOUT_SECONDS
        )
        response_data = json.loads(response_body)
        if not isinstance(response_data, dict):
            raise ValueError("Anthem returned unexpected JSON.")
        if (
            200 <= response_status < 300
            and response_data.get("success") is True
        ):
            _record_result(
                lead_id,
                status=Lead.AnthemDeliveryStatus.CONFIRMED,
                http_status=response_status,
                record_identifier=_extract_record_identifier(response_data),
            )
            return True
        _record_result(
            lead_id,
            status=Lead.AnthemDeliveryStatus.NEEDS_REVIEW,
            http_status=response_status,
            error_summary=(
                "Anthem did not confirm delivery "
                f"(HTTP {response_status}, success was not true)."
            ),
        )
        return False
    except (FutureTimeoutError, TimeoutError, socket.timeout):
        if "future" in locals():
            future.cancel()
        _record_result(
            lead_id,
            status=Lead.AnthemDeliveryStatus.NEEDS_REVIEW,
            http_status=response_status,
            error_summary=(
                "Anthem delivery timed out; check CRM before resending."
            ),
        )
        return False
    except (
        OSError,
        http.client.HTTPException,
        UnicodeDecodeError,
        json.JSONDecodeError,
        TypeError,
        ValueError,
    ):
        _record_result(
            lead_id,
            status=Lead.AnthemDeliveryStatus.NEEDS_REVIEW,
            http_status=response_status,
            error_summary=(
                "Anthem delivery failed; check CRM before resending."
            ),
        )
        return False