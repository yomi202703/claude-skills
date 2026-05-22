from __future__ import annotations

import asyncio
import os
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable

PRIORITY = {"high": 0, "normal": 1, "low": 2}


@dataclass(order=True)
class _Item:
    priority: int
    seq: int
    coro: Any = field(compare=False)
    fut: asyncio.Future[Any] = field(compare=False)


class AdaptiveRateController:
    def __init__(self, *, max_concurrency: int, latency_p95_threshold_ms: int,
                 min_concurrency: int = 1, window: int = 20):
        self.max_concurrency = max_concurrency
        self.current_concurrency = max_concurrency
        self.min_concurrency = min_concurrency
        self.threshold_ms = latency_p95_threshold_ms
        self.window = window
        self._latencies: deque[int] = deque(maxlen=window)

    def record(self, latency_ms: int) -> None:
        self._latencies.append(latency_ms)

    def observe(self) -> int:
        if len(self._latencies) < max(5, self.window // 2):
            return self.current_concurrency
        sorted_l = sorted(self._latencies)
        idx = max(0, int(0.95 * (len(sorted_l) - 1)))
        p95 = sorted_l[idx]
        if p95 > self.threshold_ms and self.current_concurrency > self.min_concurrency:
            self.current_concurrency = max(self.min_concurrency, self.current_concurrency // 2)
        elif p95 < self.threshold_ms // 2 and self.current_concurrency < self.max_concurrency:
            self.current_concurrency += 1
        return self.current_concurrency


class WorkerPool:
    def __init__(
        self,
        *,
        max_concurrency: int | None = None,
        latency_p95_threshold_ms: int | None = None,
    ):
        env_concurrency = int(os.environ.get("GEMMA_WORKER_CONCURRENCY", "4"))
        env_threshold = int(os.environ.get("GEMMA_WORKER_P95_THRESHOLD_MS", "15000"))
        self._max = max_concurrency or env_concurrency
        self._sem = asyncio.Semaphore(self._max)
        self._queue: asyncio.PriorityQueue[_Item] = asyncio.PriorityQueue()
        self._counter = 0
        self._workers: list[asyncio.Task[None]] = []
        self._closed = False
        self.rate = AdaptiveRateController(
            max_concurrency=self._max,
            latency_p95_threshold_ms=latency_p95_threshold_ms or env_threshold,
        )

    async def start(self) -> None:
        for _ in range(self._max):
            self._workers.append(asyncio.create_task(self._worker()))

    async def submit(self, coro: Awaitable[Any], *, priority: str = "normal") -> Any:
        if self._closed:
            raise RuntimeError("pool closed")
        fut: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._counter += 1
        item = _Item(
            priority=PRIORITY.get(priority, 1),
            seq=self._counter,
            coro=coro,
            fut=fut,
        )
        await self._queue.put(item)
        return await fut

    async def _worker(self) -> None:
        while True:
            item = await self._queue.get()
            if item.coro is None:
                self._queue.task_done()
                return
            async with self._sem:
                started = time.perf_counter()
                try:
                    result = await item.coro
                    if not item.fut.done():
                        item.fut.set_result(result)
                except BaseException as e:
                    if not item.fut.done():
                        item.fut.set_exception(e)
                finally:
                    elapsed_ms = int((time.perf_counter() - started) * 1000)
                    self.rate.record(elapsed_ms)
                    self.rate.observe()
                    self._queue.task_done()

    async def close(self) -> None:
        self._closed = True
        for _ in self._workers:
            await self._queue.put(_Item(priority=99, seq=10**9, coro=None, fut=asyncio.Future()))
        await asyncio.gather(*self._workers, return_exceptions=True)


async def gather_with_pool(
    pool: WorkerPool,
    factories: list[Callable[[], Awaitable[Any]]],
    *,
    priority: str = "normal",
) -> list[Any]:
    coros = [pool.submit(f(), priority=priority) for f in factories]
    return await asyncio.gather(*coros, return_exceptions=True)
