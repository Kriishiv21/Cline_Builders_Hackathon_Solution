import httpx
import pytest

from uspi.common.cline_client import ClineClient, set_client_for_testing


def test_fallback_when_no_api_key(monkeypatch):
    monkeypatch.delenv("CLINE_API_KEY", raising=False)
    monkeypatch.setenv("CLINE_API_KEY", "")
    from uspi.common.config import cline_settings
    cline_settings.cache_clear()
    client = ClineClient()
    result = client.call_structured(
        component="TEXT_SLM",
        system_prompt="sys",
        user_payload={"a": 1},
        json_schema={"type": "object"},
        fallback={"x": 1},
    )
    assert result.used_fallback is True
    assert result.data == {"x": 1}
    cline_settings.cache_clear()


def test_successful_structured_call(monkeypatch):
    monkeypatch.setenv("CLINE_API_KEY", "real-key")
    from uspi.common.config import cline_settings
    cline_settings.cache_clear()

    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"score": 0.7}'}}]
        })

    transport = httpx.MockTransport(handler)
    client = ClineClient(transport=transport)
    result = client.call_structured(
        component="TEXT_SLM",
        system_prompt="sys",
        user_payload={"a": 1},
        json_schema={"type": "object", "required": ["score"], "properties": {"score": {"type": "number"}}},
        fallback={"score": 0.5},
    )
    assert result.used_fallback is False
    assert result.data["score"] == 0.7
    cline_settings.cache_clear()


def test_invalid_json_falls_back(monkeypatch):
    monkeypatch.setenv("CLINE_API_KEY", "real-key")
    monkeypatch.setenv("CLINE_HTTP_MAX_RETRIES", "0")
    from uspi.common.config import cline_settings
    cline_settings.cache_clear()

    def handler(request):
        return httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]})

    transport = httpx.MockTransport(handler)
    client = ClineClient(transport=transport)
    result = client.call_structured(
        component="TEXT_SLM",
        system_prompt="sys",
        user_payload={},
        json_schema={"type": "object"},
        fallback={"score": 0.5},
    )
    assert result.used_fallback is True
    cline_settings.cache_clear()
