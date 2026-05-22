from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Protocol


class ConfigError(RuntimeError):
    pass


@dataclass(frozen=True)
class WorkerConfig:
    base_url: str
    api_key: str
    model: str
    provider: str
    timeout_s: float = 60.0
    max_retries: int = 3

    @classmethod
    def from_env(cls) -> "WorkerConfig":
        env = os.environ
        missing = [
            k for k in ("WORKER_LLM_BASE_URL", "WORKER_LLM_API_KEY",
                        "WORKER_LLM_MODEL", "WORKER_LLM_PROVIDER")
            if not env.get(k)
        ]
        if missing:
            raise ConfigError(f"missing env vars: {', '.join(missing)}")
        return cls(
            base_url=env["WORKER_LLM_BASE_URL"],
            api_key=env["WORKER_LLM_API_KEY"],
            model=env["WORKER_LLM_MODEL"],
            provider=env["WORKER_LLM_PROVIDER"].lower(),
        )


@dataclass
class CallResult:
    text: str
    json: dict[str, Any] | list[Any] | None
    status: str
    error: str | None = None
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    trace_id: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


class Provider(Protocol):
    name: str

    async def call(
        self,
        *,
        system: str | None,
        user: str,
        want_json: bool = False,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> CallResult: ...


def build_client(config: WorkerConfig | None = None) -> Provider:
    cfg = config or WorkerConfig.from_env()
    name = cfg.provider
    if name == "gemma":
        from gemma_worker.client.providers.gemma import GemmaProvider
        return GemmaProvider(cfg)
    if name == "openai":
        from gemma_worker.client.providers.openai_ import OpenAIProvider
        return OpenAIProvider(cfg)
    if name == "anthropic":
        from gemma_worker.client.providers.anthropic_ import AnthropicProvider
        return AnthropicProvider(cfg)
    if name == "ollama":
        from gemma_worker.client.providers.ollama import OllamaProvider
        return OllamaProvider(cfg)
    if name == "vllm":
        from gemma_worker.client.providers.vllm import VLLMProvider
        return VLLMProvider(cfg)
    raise ConfigError(f"unknown WORKER_LLM_PROVIDER: {name!r}")
