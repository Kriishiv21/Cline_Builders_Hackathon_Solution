import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

os.environ.setdefault("HASH_SALT", "test-salt-do-not-use-in-prod")
os.environ.setdefault("CLINE_API_KEY", "test-key")
os.environ.setdefault("CLINE_API_BASE", "https://api.cline.bot/api/v1")

from uspi.common.cline_client import ClineClient, ClineStructuredResult, set_client_for_testing


class StubClineClient(ClineClient):
    """Deterministic stub that returns a caller-supplied canned response,
    simulating a real Cline API round-trip without any network call."""

    def __init__(self, canned_response=None):
        self.canned_response = canned_response or {}
        self.calls = []

    def call_structured(self, *, component, system_prompt, user_payload, json_schema, fallback):
        self.calls.append({"component": component, "payload": user_payload})
        data = self.canned_response.get(component, fallback)
        return ClineStructuredResult(data=data, used_fallback=False, latency_ms=1.0, model_id=f"stub/{component}")


@pytest.fixture
def stub_cline_client():
    client = StubClineClient()
    set_client_for_testing(client)
    yield client
    set_client_for_testing(None)
