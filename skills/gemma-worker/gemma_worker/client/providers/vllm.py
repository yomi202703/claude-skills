from __future__ import annotations

from gemma_worker.client.base import CallResult, WorkerConfig
from gemma_worker.client._shared import call_chat, make_client


class VLLMProvider:
    name = "vllm"

    def __init__(self, cfg: WorkerConfig):
        self.cfg = cfg
        self._client = make_client(cfg)

    async def call(
        self,
        *,
        system: str | None,
        user: str,
        want_json: bool = False,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> CallResult:
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        if want_json:
            user = user + "\n\nReturn ONLY valid JSON. No prose, no code fences."
        messages.append({"role": "user", "content": user})
        return await call_chat(
            client=self._client,
            model=self.cfg.model,
            messages=messages,
            max_retries=self.cfg.max_retries,
            temperature=temperature,
            max_tokens=max_tokens,
            want_json=want_json,
            system_name=self.name,
        )
