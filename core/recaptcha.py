import http.client
import json
import math
import socket
from dataclasses import dataclass
from urllib.parse import urlencode


VERIFY_HOST = "www.google.com"
VERIFY_PATH = "/recaptcha/api/siteverify"
EXPECTED_ACTION = "contact_form"
CONNECT_TIMEOUT_SECONDS = 3
READ_TIMEOUT_SECONDS = 7
MAX_RESPONSE_BYTES = 32_768
_CONFIG_NOT_PROVIDED = object()


@dataclass(frozen=True)
class RecaptchaConfig:
    site_key: str
    secret_key: str
    minimum_score: float
    allowed_hostnames: frozenset[str]


def get_contact_recaptcha_config():
    from .models import RecaptchaIntegration

    integration = RecaptchaIntegration.objects.filter(
        singleton_key="default",
        is_enabled=True,
    ).first()
    if not integration:
        return None
    return RecaptchaConfig(
        site_key=integration.site_key,
        secret_key=integration.get_secret_key(),
        minimum_score=float(integration.minimum_score),
        allowed_hostnames=frozenset(integration.normalized_hostnames),
    )


def verify_contact_recaptcha(token, config=_CONFIG_NOT_PROVIDED):
    if config is _CONFIG_NOT_PROVIDED:
        config = get_contact_recaptcha_config()
    if config is None:
        return True
    if (
        not isinstance(token, str)
        or not token
        or not isinstance(config.site_key, str)
        or not config.site_key.strip()
        or not isinstance(config.secret_key, str)
        or not config.secret_key.strip()
        or not isinstance(config.allowed_hostnames, frozenset)
        or not config.allowed_hostnames
        or any(
            not isinstance(hostname, str) or not hostname
            for hostname in config.allowed_hostnames
        )
        or isinstance(config.minimum_score, bool)
        or not isinstance(config.minimum_score, (int, float))
        or not math.isfinite(config.minimum_score)
        or not 0 <= config.minimum_score <= 1
    ):
        return False

    body = urlencode(
        {"secret": config.secret_key, "response": token}
    ).encode("utf-8")
    connection = http.client.HTTPSConnection(
        VERIFY_HOST,
        443,
        timeout=CONNECT_TIMEOUT_SECONDS,
    )
    try:
        connection.connect()
        connection.sock.settimeout(READ_TIMEOUT_SECONDS)
        connection.request(
            "POST",
            VERIFY_PATH,
            body=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
            },
        )
        response = connection.getresponse()
        response_body = response.read(MAX_RESPONSE_BYTES + 1)
        if response.status != 200 or len(response_body) > MAX_RESPONSE_BYTES:
            return False
        result = json.loads(response_body)
        if not isinstance(result, dict):
            return False
        score = result.get("score")
        action = result.get("action")
        hostname = result.get("hostname")
        if (
            isinstance(score, bool)
            or not isinstance(score, (int, float))
            or not isinstance(action, str)
            or not isinstance(hostname, str)
        ):
            return False
        if not math.isfinite(score) or not 0 <= score <= 1:
            return False
        return (
            result.get("success") is True
            and action == EXPECTED_ACTION
            and score >= config.minimum_score
            and hostname.lower() in config.allowed_hostnames
        )
    except (
        OSError,
        TimeoutError,
        socket.timeout,
        http.client.HTTPException,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ):
        return False
    finally:
        connection.close()