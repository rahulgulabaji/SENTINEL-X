"""Tests for app.services.analysis_service.sanitize_error_message -- the
redaction/truncation applied to a job's `error` field before it is stored
and, by extension, before it is ever returned via
GET /v1/analysis/{job_id}/result.

Same no-conftest.py, path-injection boilerplate as the other test files in
this directory. Does not touch MongoDB or the inference pipeline -- this is
a pure-function test of the sanitizer only.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.analysis_service import (  # noqa: E402
    _MAX_SANITIZED_ERROR_LENGTH,
    sanitize_error_message,
)


def _patch_secrets(monkeypatch, *, mongodb_uri: str = "", sms_password: str = "") -> None:
    """Points get_settings() at a throwaway Settings instance with just the
    two secret fields set, leaving everything else at the real settings'
    values -- mirrors test_mongodb.py's dataclasses.replace(get_settings(), ...)
    pattern used for the same reason (Settings is a frozen dataclass)."""
    import dataclasses

    patched = dataclasses.replace(
        get_settings(),
        MONGODB_URI=mongodb_uri,
        SMS_GATEWAY_PASSWORD=sms_password,
    )
    monkeypatch.setattr("app.services.analysis_service.get_settings", lambda: patched)


def test_plain_message_passes_through_with_exception_type_prefix(monkeypatch):
    _patch_secrets(monkeypatch)
    exc = ValueError("invalid literal for int() with base 10: 'nan'")
    result = sanitize_error_message(exc)
    assert result == "ValueError: invalid literal for int() with base 10: 'nan'"


def test_configured_mongodb_uri_is_redacted_even_without_uri_shape(monkeypatch):
    secret_uri = "mongodb+srv://realuser:realpass123@cluster0.abcde.mongodb.net/sentinel_x"
    _patch_secrets(monkeypatch, mongodb_uri=secret_uri)
    exc = ConnectionError(f"Could not connect to {secret_uri}: timeout")
    result = sanitize_error_message(exc)
    assert secret_uri not in result
    assert "realuser" not in result
    assert "realpass123" not in result
    # Diagnostic context (the exception type, and that it was a connection
    # failure) must survive the redaction, not just the secret disappearing.
    assert "ConnectionError" in result
    assert "timeout" in result


def test_configured_sms_password_is_redacted(monkeypatch):
    _patch_secrets(monkeypatch, sms_password="topsecretpw")
    exc = RuntimeError("Auth failed with password topsecretpw for gateway")
    result = sanitize_error_message(exc)
    assert "topsecretpw" not in result
    assert "Auth failed with password *** for gateway" in result


def test_any_credential_bearing_uri_is_redacted_by_shape_not_just_configured_secrets(monkeypatch):
    """A URI with credentials that do NOT match any currently-configured
    secret must still be redacted -- the regex-based pass is the general
    safety net; the exact-match pass is only the belt-and-suspenders
    addition for the two secrets this app actually configures."""
    _patch_secrets(monkeypatch)
    exc = RuntimeError("http://attacker:hunter2@evil.example.com/path failed")
    result = sanitize_error_message(exc)
    assert "attacker" not in result
    assert "hunter2" not in result
    # Host/path are retained -- useful diagnostic detail, not a secret.
    assert "evil.example.com/path" in result
    assert "failed" in result


def test_uri_with_no_credentials_is_left_alone(monkeypatch):
    _patch_secrets(monkeypatch)
    exc = RuntimeError("GET http://example.com/health returned 503")
    result = sanitize_error_message(exc)
    assert "http://example.com/health" in result


def test_long_message_is_truncated_to_max_length(monkeypatch):
    _patch_secrets(monkeypatch)
    exc = ValueError("x" * 1000)
    result = sanitize_error_message(exc)
    assert len(result) == _MAX_SANITIZED_ERROR_LENGTH
    assert result.endswith("...")


def test_short_message_is_not_padded_or_altered_in_length(monkeypatch):
    _patch_secrets(monkeypatch)
    exc = ValueError("short")
    result = sanitize_error_message(exc)
    assert len(result) < _MAX_SANITIZED_ERROR_LENGTH
    assert not result.endswith("...")


def test_empty_exception_message_still_yields_exception_type(monkeypatch):
    _patch_secrets(monkeypatch)
    exc = ValueError()
    result = sanitize_error_message(exc)
    assert result == "ValueError"


def test_sanitizer_never_raises_even_if_settings_lookup_fails(monkeypatch):
    """Sanitization failing must never be the reason a job's genuine
    failure goes unrecorded -- confirms the fallback placeholder path."""

    def _broken_settings():
        raise RuntimeError("settings unavailable")

    monkeypatch.setattr("app.services.analysis_service.get_settings", _broken_settings)
    exc = ValueError("whatever")
    result = sanitize_error_message(exc)
    assert result == "Internal error (details withheld)."


def test_custom_max_length_is_honored(monkeypatch):
    _patch_secrets(monkeypatch)
    exc = ValueError("a" * 50)
    result = sanitize_error_message(exc, max_length=20)
    assert len(result) == 20
    assert result.endswith("...")
