"""
SMS Gateway service -- an isolated integration with an Android phone acting
as a physical SMS modem (e.g. via an "SMS Gateway" style Android app that
exposes a local HTTP API), reached over local Wi-Fi/hotspot.

Architecture (see notifications.py route):

    SENTINEL-X backend -> this service -> Android phone (local HTTP) -> carrier SMS

This module is intentionally self-contained and knows nothing about
inference, anomalies, jobs, or the analysis pipeline. It is NOT wired into
analysis_service/job_executor in this step -- the only caller is the
isolated /api/v1/notifications test endpoint. A later step may call
send_sms() from elsewhere, but that wiring does not belong here.

Uses only the stdlib HTTP client (urllib) rather than adding a new HTTP
dependency (requests/httpx are not declared direct dependencies of this
project) -- appropriate for the low request volume of this feature.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from app.core.config import Settings

logger = logging.getLogger(__name__)

# Loose E.164-ish check: optional leading +, 7-15 digits total. Intentionally
# permissive about numbering-plan details -- real validation/formatting is
# the carrier's job; this just rejects obviously-malformed input (empty,
# letters, way too short/long) before we ever construct a request.
_PHONE_RE = re.compile(r"^\+?[0-9]{7,15}$")

_REQUEST_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class SmsResult:
    """Structured outcome of a send_sms()/check_connectivity() call. Never
    raises on an unreachable gateway -- callers get this back instead."""

    success: bool
    message: str
    error: str | None = None

    def to_dict(self) -> dict:
        d: dict = {"success": self.success, "message": self.message}
        if self.error is not None:
            d["error"] = self.error
        return d


class SmsGatewayNotConfiguredError(Exception):
    """Raised internally when configuration is missing/invalid; always
    caught within this module and turned into a failed SmsResult -- never
    propagates to callers."""


def _validate_recipient(recipient: str) -> str:
    candidate = (recipient or "").strip()
    if not _PHONE_RE.match(candidate):
        raise ValueError(
            "Invalid recipient phone number format. Expected digits only, "
            "optionally prefixed with '+', 7-15 digits total."
        )
    return candidate


def _mask_phone(number: str) -> str:
    """Last 2 digits visible, everything else masked -- used only in log
    lines, never in API responses (callers get the structured result, not
    this)."""
    if len(number) <= 2:
        return "*" * len(number)
    return "*" * (len(number) - 2) + number[-2:]


class SmsGatewayService:
    """Thin client for an Android-phone-hosted SMS gateway HTTP API.

    Configuration is read from Settings (env-var backed, see
    app/core/config.py) -- never hardcoded, never logged in full.
    """

    def __init__(self, settings: Settings):
        self._settings = settings

    # -- public status (safe to expose over HTTP) --------------------------

    def is_enabled(self) -> bool:
        return self._settings.SMS_GATEWAY_ENABLED

    def is_configured(self) -> bool:
        """True iff enabled AND the minimum required settings are present.
        Does not attempt any network call."""
        if not self._settings.SMS_GATEWAY_ENABLED:
            return False
        return bool(self._settings.SMS_GATEWAY_URL)

    # -- internal: build + fire the HTTP request ---------------------------

    def _require_configured(self) -> None:
        if not self._settings.SMS_GATEWAY_ENABLED:
            raise SmsGatewayNotConfiguredError("SMS gateway is disabled (SMS_GATEWAY_ENABLED=false).")
        if not self._settings.SMS_GATEWAY_URL:
            raise SmsGatewayNotConfiguredError("SMS_GATEWAY_URL is not set.")

    def _build_request(self, recipient: str, message: str) -> urllib.request.Request:
        # Real API contract for the "SMS Gateway for Android" app's Local
        # Server mode (capcom6/android-sms-gateway), verified against
        # https://docs.sms-gate.app/getting-started/local-server/ and the
        # project README -- NOT /send with {phoneNumber, message} as
        # originally (incorrectly) assumed in Step 1.
        url = self._settings.SMS_GATEWAY_URL.rstrip("/") + "/message"
        payload = json.dumps(
            {"textMessage": {"text": message}, "phoneNumbers": [recipient]}
        ).encode("utf-8")

        headers = {"Content-Type": "application/json"}
        username = self._settings.SMS_GATEWAY_USERNAME
        password = self._settings.SMS_GATEWAY_PASSWORD
        if username or password:
            token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
            headers["Authorization"] = f"Basic {token}"

        return urllib.request.Request(url, data=payload, headers=headers, method="POST")

    def _send_request(self, request: urllib.request.Request) -> tuple[int, str]:
        with urllib.request.urlopen(request, timeout=_REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace")
            return response.status, body

    # -- public API ----------------------------------------------------------

    def send_sms(self, recipient: str, message: str) -> SmsResult:
        """Sends exactly one SMS via the Android gateway. Never raises --
        all failure modes (misconfiguration, bad input, unreachable phone,
        non-2xx response, timeout) are caught and returned as a failed
        SmsResult so this can never crash the calling FastAPI request."""
        try:
            self._require_configured()
            clean_recipient = _validate_recipient(recipient)
            clean_message = (message or "").strip()
            if not clean_message:
                return SmsResult(success=False, message="SMS not sent.", error="Message body is empty.")

            request = self._build_request(clean_recipient, clean_message)
            status_code, _body = self._send_request(request)

            if 200 <= status_code < 300:
                logger.info("SMS sent to %s via gateway (status %s).", _mask_phone(clean_recipient), status_code)
                return SmsResult(success=True, message="SMS queued.")

            logger.warning("SMS gateway returned non-2xx status %s for %s.", status_code, _mask_phone(clean_recipient))
            return SmsResult(
                success=False,
                message="SMS not sent.",
                error=f"Gateway responded with HTTP {status_code}.",
            )

        except SmsGatewayNotConfiguredError as exc:
            return SmsResult(success=False, message="SMS not sent.", error=str(exc))
        except ValueError as exc:
            return SmsResult(success=False, message="SMS not sent.", error=str(exc))
        except urllib.error.HTTPError as exc:
            logger.warning("SMS gateway HTTP error: %s", exc)
            return SmsResult(success=False, message="SMS not sent.", error=f"Gateway HTTP error: {exc.code}")
        except urllib.error.URLError as exc:
            logger.warning("SMS gateway unreachable: %s", exc)
            return SmsResult(success=False, message="SMS not sent.", error="SMS gateway unreachable.")
        except TimeoutError:
            logger.warning("SMS gateway request timed out.")
            return SmsResult(success=False, message="SMS not sent.", error="SMS gateway request timed out.")
        except Exception as exc:  # noqa: BLE001 -- last-resort guard, see module docstring
            logger.exception("Unexpected error sending SMS.")
            return SmsResult(success=False, message="SMS not sent.", error=f"Unexpected error: {exc}")

    def check_connectivity(self) -> SmsResult:
        """Lightweight reachability probe, used by the status endpoint so it
        never claims to be "connected" without an actual successful check.
        Does not send an SMS.

        Targets /docs (the app's Swagger UI) rather than the bare base URL:
        the real Local Server API has no dedicated health-check endpoint
        (verified against the project's docs/README -- the only documented
        GET path is /docs), so this is the one path guaranteed to exist.
        """
        try:
            self._require_configured()
            url = self._settings.SMS_GATEWAY_URL.rstrip("/") + "/docs"
            request = urllib.request.Request(url, method="GET")
            username = self._settings.SMS_GATEWAY_USERNAME
            password = self._settings.SMS_GATEWAY_PASSWORD
            if username or password:
                token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
                request.add_header("Authorization", f"Basic {token}")

            status_code, _body = self._send_request(request)
            # urlopen() only returns normally for 2xx -- any non-2xx raises
            # HTTPError instead (caught below), so this branch is reached
            # for 2xx only. Kept as a defensive check in case that ever
            # changes, not because it's expected to see a non-2xx here.
            if 200 <= status_code < 500:
                return SmsResult(success=True, message="Gateway reachable.")
            return SmsResult(success=False, message="Gateway unreachable.", error=f"HTTP {status_code}")

        except SmsGatewayNotConfiguredError as exc:
            return SmsResult(success=False, message="Gateway not configured.", error=str(exc))
        except urllib.error.HTTPError as exc:
            # HTTPError is a URLError subclass but means the opposite thing:
            # the server answered (phone is reachable) and rejected the
            # request (e.g. 401 for a wrong/missing password). Must be
            # caught before the URLError branch below, which it would
            # otherwise match and misreport as "unreachable". Any status
            # code at all here proves reachability -- this check answers
            # "can we reach the phone", not "is our auth valid".
            logger.info("SMS gateway responded with HTTP %s (reachable).", exc.code)
            return SmsResult(success=True, message="Gateway reachable.", error=f"HTTP {exc.code} (auth not verified).")
        except (urllib.error.URLError, TimeoutError) as exc:
            logger.info("SMS gateway connectivity check failed: %s", exc)
            return SmsResult(success=False, message="Gateway unreachable.", error="SMS gateway unreachable.")
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error checking SMS gateway connectivity.")
            return SmsResult(success=False, message="Gateway unreachable.", error=f"Unexpected error: {exc}")


_service: SmsGatewayService | None = None


def get_sms_gateway_service(settings: Settings | None = None) -> SmsGatewayService:
    """Process-wide SmsGatewayService instance, same singleton-via-function
    pattern as get_settings()/get_pipeline() elsewhere in this codebase."""
    global _service
    if settings is not None:
        return SmsGatewayService(settings)
    if _service is None:
        from app.core.config import get_settings

        _service = SmsGatewayService(get_settings())
    return _service
