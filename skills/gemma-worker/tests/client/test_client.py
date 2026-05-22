from __future__ import annotations

import json

import httpx
import pytest
import respx

from gemma_worker.client._shared import strip_code_fence, try_parse_json
from gemma_worker.client.base import ConfigError, WorkerConfig, build_client
from gemma_worker.client.providers.gemma import _merge_system_into_user


def test_strip_code_fence_simple():
    assert strip_code_fence("```json\n{\"a\":1}\n```") == '{"a":1}'
    assert strip_code_fence("```\n[]\n```") == "[]"
    assert strip_code_fence("plain") == "plain"


def test_try_parse_json_pure():
    assert try_parse_json('{"x":1}') == {"x": 1}
    assert try_parse_json("[1,2,3]") == [1, 2, 3]


def test_try_parse_json_fenced():
    assert try_parse_json("```json\n{\"k\":\"v\"}\n```") == {"k": "v"}


def test_try_parse_json_embedded():
    payload = "Sure, here is the answer: {\"verdict\":\"PROMOTE\"} thanks"
    assert try_parse_json(payload) == {"verdict": "PROMOTE"}


def test_try_parse_json_invalid():
    assert try_parse_json("not json at all") is None


def test_merge_system_into_user_basic():
    merged = _merge_system_into_user("be terse", "do X", want_json=False)
    assert "be terse" in merged
    assert "do X" in merged
    assert "---" in merged


def test_merge_system_into_user_json_hint():
    merged = _merge_system_into_user(None, "give list", want_json=True)
    assert "give list" in merged
    assert "Return ONLY a valid JSON" in merged
    assert "Begin your response with {" in merged


def test_config_from_env_missing(monkeypatch):
    for k in ("WORKER_LLM_BASE_URL", "WORKER_LLM_API_KEY",
              "WORKER_LLM_MODEL", "WORKER_LLM_PROVIDER"):
        monkeypatch.delenv(k, raising=False)
    with pytest.raises(ConfigError):
        WorkerConfig.from_env()


def test_config_from_env_present(monkeypatch):
    monkeypatch.setenv("WORKER_LLM_BASE_URL", "https://x/v1")
    monkeypatch.setenv("WORKER_LLM_API_KEY", "sk")
    monkeypatch.setenv("WORKER_LLM_MODEL", "m")
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "GEMMA")
    cfg = WorkerConfig.from_env()
    assert cfg.provider == "gemma"


def test_build_client_unknown_provider(mock_env, monkeypatch):
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "unknown-foo")
    with pytest.raises(ConfigError):
        build_client()


@pytest.mark.parametrize("provider", ["gemma", "openai", "ollama", "vllm", "anthropic"])
def test_build_client_all_providers(mock_env, monkeypatch, provider):
    monkeypatch.setenv("WORKER_LLM_PROVIDER", provider)
    cli = build_client()
    assert cli.name == provider


@pytest.mark.asyncio
async def test_gemma_call_roundtrip(mock_env, monkeypatch):
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "gemma")
    monkeypatch.setenv("WORKER_LLM_BASE_URL", "https://mock.invalid/v1")
    client = build_client()

    payload = {
        "id": "chatcmpl-x",
        "object": "chat.completion",
        "model": "gemma-test",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": '{"verdict":"PROMOTE"}'},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
    }
    with respx.mock(base_url="https://mock.invalid/v1") as router:
        route = router.post("/chat/completions").mock(
            return_value=httpx.Response(200, json=payload)
        )
        result = await client.call(system="be brief", user="check it", want_json=True)
        assert route.called
        sent = json.loads(route.calls.last.request.content)
        assert all(m["role"] == "user" for m in sent["messages"])
        assert "be brief" in sent["messages"][0]["content"]
        assert "check it" in sent["messages"][0]["content"]

    assert result.status == "ok"
    assert result.json == {"verdict": "PROMOTE"}
    assert result.tokens_in == 10
    assert result.tokens_out == 5


@pytest.mark.asyncio
async def test_openai_call_keeps_system_role(mock_env, monkeypatch):
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "openai")
    monkeypatch.setenv("WORKER_LLM_BASE_URL", "https://mock.invalid/v1")
    client = build_client()
    payload = {
        "id": "x",
        "object": "chat.completion",
        "model": "m",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "ok"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    with respx.mock(base_url="https://mock.invalid/v1") as router:
        route = router.post("/chat/completions").mock(
            return_value=httpx.Response(200, json=payload)
        )
        await client.call(system="S", user="U")
        sent = json.loads(route.calls.last.request.content)
        roles = [m["role"] for m in sent["messages"]]
        assert roles == ["system", "user"]


@pytest.mark.asyncio
async def test_json_parse_failure_status_error(mock_env, monkeypatch):
    monkeypatch.setenv("WORKER_LLM_PROVIDER", "gemma")
    monkeypatch.setenv("WORKER_LLM_BASE_URL", "https://mock.invalid/v1")
    client = build_client()
    payload = {
        "id": "x",
        "object": "chat.completion",
        "model": "m",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": "definitely not json"}, "finish_reason": "stop"}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }
    with respx.mock(base_url="https://mock.invalid/v1") as router:
        router.post("/chat/completions").mock(return_value=httpx.Response(200, json=payload))
        result = await client.call(system=None, user="x", want_json=True)
    assert result.status == "error"
    assert result.error == "json_parse_failed"
