from __future__ import annotations

from gemma_worker.client.base import CallResult, WorkerConfig
from gemma_worker.client._shared import call_chat, make_client


class GemmaProvider:
    name = "gemma"

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
        merged = _merge_system_into_user(system, user, want_json=want_json)
        messages = [{"role": "user", "content": merged}]
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


def _merge_system_into_user(system: str | None, user: str, *, want_json: bool) -> str:
    parts: list[str] = []
    if system:
        parts.append(system.strip())
        parts.append("---")
    parts.append(user.strip())
    if want_json:
        parts.append("")
        parts.append("Return ONLY a valid JSON value. No prose, no code fences, no preamble.")
        parts.append("Begin your response with { or [ and nothing else.")
    return "\n\n".join(parts)
