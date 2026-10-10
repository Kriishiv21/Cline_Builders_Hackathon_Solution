"""The single shared Cline API client.

Per the task instructions: every place in the architecture document that
calls for *training* a model (the text Stage-3 SLM, the AASIST spoof
branch, the phonetic/formant branch, the live voice-authenticity adapter,
the content-risk classifier) is replaced here by a structured call to the
**Cline API** using an API key, instead of a locally trained model. This
module is the only place in the whole codebase allowed to perform that
HTTP call (enforced by tests/test_no_direct_http.py), matching the
architecture's own rule that LLM calls must be isolated behind one
component so "Deterministic decisions live in the backend" (principle 4)
and the Cline usage boundaries in section 10 (DEV / AUTO / RUNTIME).

Contract:
  - Input: a component name (routes to a per-component model id), a system
    prompt describing exactly what structured signal to produce, a JSON
    payload of *already redacted/hashed* case data, and a JSON schema the
    reply must satisfy.
  - Output: a dict matching the schema, with one retry on invalid JSON and
    a documented deterministic fallback signal (`score_semantics =
    "unavailable"`) if the Cline API cannot be reached or never returns
    valid JSON. The fallback is NEVER silently treated as "safe" (principle
    3, "Missing is neither safe nor risky").
  - Raw audio and full transcripts never pass through this client; callers
    must pre-redact per architecture section 11.1 (text injection /
    privacy threat model) before calling.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional

import httpx
from jsonschema import Draft202012Validator

from uspi.common.config import cline_settings

logger = logging.getLogger(__name__)


class ClineUnavailableError(Exception):
    """Raised internally; callers should prefer the fallback signal instead
    of letting this escape into a scoring path (no crash-to-alert)."""


@dataclass
class ClineStructuredResult:
    data: Dict[str, Any]
    used_fallback: bool
    latency_ms: float
    model_id: str
    raw_text: Optional[str] = None


def _extract_json_block(text: str) -> Dict[str, Any]:
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("No JSON object found in Cline response")


class ClineClient:
    """Thin wrapper over the Cline API chat/completions endpoint.

    Uses an OpenAI-compatible `/chat/completions` contract, matching the
    architecture doc's reference endpoint
    `https://api.cline.bot/api/v1/chat/completions` (section 10.3).
    """

    def __init__(self, transport: Optional[httpx.BaseTransport] = None) -> None:
        self.settings = cline_settings()
        self._transport = transport

    def _client(self) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.api_base,
            timeout=self.settings.timeout_seconds,
            transport=self._transport,
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
        )

    def call_structured(
        self,
        *,
        component: str,
        system_prompt: str,
        user_payload: Dict[str, Any],
        json_schema: Dict[str, Any],
        fallback: Dict[str, Any],
    ) -> ClineStructuredResult:
        """Call the Cline API and return a schema-validated dict, or a
        documented fallback (never silently promoted to "safe")."""
        model_id = self.settings.model_for(component)
        validator = Draft202012Validator(json_schema)
        start = time.monotonic()

        if not self.settings.api_key:
            logger.warning(
                "CLINE_API_KEY not set; component=%s returning unavailable fallback",
                component,
            )
            return ClineStructuredResult(
                data=fallback, used_fallback=True, latency_ms=0.0, model_id=model_id
            )

        body = {
            "model": model_id,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": json.dumps(user_payload)},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        }

        last_error: Optional[Exception] = None
        for attempt in range(self.settings.max_retries + 1):
            try:
                with self._client() as client:
                    resp = client.post("/chat/completions", json=body)
                    resp.raise_for_status()
                    payload = resp.json()
                content = payload["choices"][0]["message"]["content"]
                parsed = _extract_json_block(content)
                errors = sorted(validator.iter_errors(parsed), key=str)
                if errors:
                    raise ValueError(f"Schema validation failed: {errors[0].message}")
                latency_ms = (time.monotonic() - start) * 1000.0
                return ClineStructuredResult(
                    data=parsed,
                    used_fallback=False,
                    latency_ms=latency_ms,
                    model_id=model_id,
                    raw_text=content,
                )
            except Exception as exc:  # noqa: BLE001 - broad by design, isolated here
                last_error = exc
                logger.warning(
                    "Cline call failed (component=%s attempt=%d/%d): %s",
                    component,
                    attempt + 1,
                    self.settings.max_retries + 1,
                    exc,
                )

        latency_ms = (time.monotonic() - start) * 1000.0
        logger.error(
            "Cline API exhausted retries for component=%s, using fallback: %s",
            component,
            last_error,
        )
        return ClineStructuredResult(
            data=fallback, used_fallback=True, latency_ms=latency_ms, model_id=model_id
        )


_default_client: Optional[ClineClient] = None


def get_client() -> ClineClient:
    global _default_client
    if _default_client is None:
        _default_client = ClineClient()
    return _default_client


def set_client_for_testing(client: ClineClient) -> None:
    global _default_client
    _default_client = client

