"""
Grok (xAI)-backed incident summarizer -- an isolated AI-summary feature
layered on top of the existing deterministic summary builder
(app/services/incident_summary_service.py), which remains unchanged and is
the ONLY source of fact fed to the model. This module never sends a raw
incident/job document to xAI -- only the already-honest, already-structured
shape build_incident_summary() produces (ai_detected/verified_facts/
evidence/location/limitations), so Grok can never see or invent fields that
shape doesn't already contain.

Same discipline as app/services/sms_gateway.py: never raises outward. Every
call site gets back a GrokSummaryResult, success or not. When xAI is
disabled, unconfigured, or the live call fails for any reason (timeout,
non-2xx, rate limit, network error), this falls back to a deterministic,
non-LLM summary built from the same structured shape -- never a fabricated
"AI-generated" sentence pretending to be a real model response, and never a
silently empty/successful result when the call actually failed.

Caching: a small bounded in-process cache keyed on (incident_id, updated_at)
avoids calling Grok again for the same incident on every dashboard
poll/render -- a real concern since this app has no SSR/edge cache layer.
Not a general-purpose cache; just enough to stop a chatty frontend from
re-summarizing an unchanged incident on every tick. force_refresh=True
bypasses it for an explicit operator-triggered "Refresh".
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Literal

import httpx

from app.core.config import Settings
from app.services.incident_summary_service import build_incident_summary

logger = logging.getLogger(__name__)

_XAI_CHAT_COMPLETIONS_URL = "https://api.x.ai/v1/chat/completions"

# Bounded so this never grows unboundedly across a long-running process --
# this app only ever cares about "the latest incident" today, so a handful
# of recent entries is already generous headroom.
_MAX_CACHE_ENTRIES = 8

_SYSTEM_PROMPT = (
    "You are an incident summarization assistant for a physical security "
    "operations dashboard. You will be given a JSON object with two kinds "
    "of fields: `ai_detected` (model predictions from a video-analysis "
    "pipeline -- may be wrong or low-confidence) and `verified_facts` "
    "(operational record fields, treated as ground truth). "
    "Write a concise, professional 3-6 sentence incident summary in plain "
    "prose (no markdown headers, no bullet lists). Clearly distinguish "
    "model predictions from confirmed facts (e.g. phrase detected activity "
    "as 'the system flagged' or 'detected with X% confidence', not as "
    "settled fact). If anomaly_probability or action_confidence is low, or "
    "evidence/location is unavailable, explicitly state that uncertainty. "
    "Mention the likely action, the evidence window if available, and the "
    "location if available. "
    "Never invent people, names, addresses, GPS coordinates, additional "
    "events, police or responder actions, dispatch status, or verification "
    "status that is not present in the given JSON. If a field is null or "
    "missing, say it is unavailable rather than guessing a value. "
    "Output only the summary text, nothing else."
)


@dataclass(frozen=True)
class GrokSummaryResult:
    """Structured outcome of summarize_incident(). Never raises -- callers
    always get one of these back, with `source` telling them plainly
    whether `summary_text` actually came from Grok or is the honest
    deterministic fallback."""

    success: bool
    summary_text: str | None
    source: Literal["grok", "fallback"]
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "summary_text": self.summary_text,
            "source": self.source,
            "error": self.error,
        }


def _deterministic_fallback_text(structured_summary: dict[str, Any]) -> str:
    """Builds a short, honest, non-LLM summary straight from the structured
    shape's own fields -- used whenever Grok is disabled, unconfigured, or
    the live call fails. Never claims to be AI-generated; just states the
    real fields plainly, same honesty discipline as the shape itself."""
    ai = structured_summary.get("ai_detected") or {}
    headline = structured_summary.get("headline") or "An incident was recorded."

    likely_action = ai.get("likely_action")
    anomaly_probability = ai.get("anomaly_probability")
    action_confidence = ai.get("action_confidence")

    action_text = f"Likely action: {likely_action}." if likely_action else "Likely action: not determined."
    anomaly_text = (
        f"Anomaly probability: {anomaly_probability * 100:.1f}%."
        if anomaly_probability is not None
        else "Anomaly probability: unavailable."
    )
    confidence_text = (
        f"Action confidence: {action_confidence * 100:.1f}%."
        if action_confidence is not None
        else "Action confidence: unavailable."
    )

    evidence = structured_summary.get("evidence")
    if evidence and evidence.get("available"):
        start = evidence.get("window_start_seconds")
        end = evidence.get("window_end_seconds")
        evidence_text = f"Evidence window: {start:.2f}s-{end:.2f}s." if start is not None and end is not None else ""
    else:
        evidence_text = "Evidence window: unavailable."

    location = structured_summary.get("location") or {}
    location_text = f"Location: {location.get('label')}." if location.get("available") and location.get("label") else "Location: unavailable."

    limitations = structured_summary.get("limitations") or []
    limitations_text = " ".join(limitations)

    parts = [headline, action_text, anomaly_text, confidence_text, evidence_text, location_text, limitations_text]
    return " ".join(p for p in parts if p)


class GrokSummaryService:
    """Thin client for xAI's chat-completions API, scoped to summarization
    only -- it is never given dispatch tools, action authority, or any
    identity to act under. Configuration is read from Settings (env-var
    backed, see app/core/config.py); the API key is never logged or
    returned from any public method."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._cache: dict[tuple[str, Any], GrokSummaryResult] = {}
        self._cache_order: list[tuple[str, Any]] = []

    def is_configured(self) -> bool:
        """True iff enabled AND a key is present. Does not attempt any
        network call -- safe to expose over HTTP as a status flag."""
        return self._settings.GROK_ENABLED and bool(self._settings.XAI_API_KEY)

    def _cache_key(self, incident: dict[str, Any]) -> tuple[str, Any]:
        return (incident.get("incident_id") or "", incident.get("updated_at") or incident.get("created_at"))

    def _cache_put(self, key: tuple[str, Any], result: GrokSummaryResult) -> None:
        if key in self._cache:
            self._cache_order.remove(key)
        self._cache[key] = result
        self._cache_order.append(key)
        while len(self._cache_order) > _MAX_CACHE_ENTRIES:
            oldest = self._cache_order.pop(0)
            self._cache.pop(oldest, None)

    def _call_xai(self, structured_summary: dict[str, Any]) -> str:
        """Raises on any failure (timeout, non-2xx, malformed response) --
        caught by the single call site in summarize_incident(). Never
        called when the service isn't configured."""
        payload = {
            "model": self._settings.GROK_MODEL,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(structured_summary)},
            ],
            "temperature": 0.2,
        }
        headers = {
            "Authorization": f"Bearer {self._settings.XAI_API_KEY}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=self._settings.GROK_TIMEOUT_SECONDS) as client:
            response = client.post(_XAI_CHAT_COMPLETIONS_URL, json=payload, headers=headers)
        if response.status_code == 429:
            raise RuntimeError("xAI API rate limit exceeded (HTTP 429).")
        response.raise_for_status()
        body = response.json()
        content = body["choices"][0]["message"]["content"]
        if not content or not content.strip():
            raise RuntimeError("xAI API returned an empty summary.")
        return content.strip()

    def summarize_incident(
        self,
        incident: dict[str, Any],
        job: dict[str, Any] | None,
        *,
        force_refresh: bool = False,
    ) -> GrokSummaryResult:
        """Summarizes a real incident + its linked job (job may be None).
        Always returns a GrokSummaryResult -- never raises. `source` tells
        the caller plainly whether this came from a real Grok call
        ("grok") or the deterministic fallback ("fallback"); a caller must
        never present a fallback result as if it were AI-generated."""
        structured_summary = build_incident_summary(incident, job)

        cache_key = self._cache_key(incident)
        if not force_refresh and cache_key in self._cache:
            return self._cache[cache_key]

        if not self.is_configured():
            result = GrokSummaryResult(
                success=False,
                summary_text=_deterministic_fallback_text(structured_summary),
                source="fallback",
                error="Grok summarization is not enabled or XAI_API_KEY is not configured.",
            )
            self._cache_put(cache_key, result)
            return result

        try:
            summary_text = self._call_xai(structured_summary)
            result = GrokSummaryResult(success=True, summary_text=summary_text, source="grok", error=None)
        except httpx.TimeoutException:
            logger.warning("Grok summary request timed out.")
            result = GrokSummaryResult(
                success=False,
                summary_text=_deterministic_fallback_text(structured_summary),
                source="fallback",
                error="xAI API request timed out.",
            )
        except httpx.HTTPStatusError as exc:
            logger.warning("Grok summary request failed with HTTP %s.", exc.response.status_code)
            result = GrokSummaryResult(
                success=False,
                summary_text=_deterministic_fallback_text(structured_summary),
                source="fallback",
                error=f"xAI API returned HTTP {exc.response.status_code}.",
            )
        except Exception as exc:  # noqa: BLE001 -- last-resort guard, see module docstring
            logger.exception("Unexpected error calling Grok for incident summarization.")
            result = GrokSummaryResult(
                success=False,
                summary_text=_deterministic_fallback_text(structured_summary),
                source="fallback",
                error=f"Unexpected error: {exc}",
            )

        self._cache_put(cache_key, result)
        return result
