from __future__ import annotations

import asyncio

import pytest

from gemma_worker.queue.worker_pool import (
    AdaptiveRateController,
    WorkerPool,
    gather_with_pool,
)


@pytest.mark.asyncio
async def test_pool_runs_tasks():
    pool = WorkerPool(max_concurrency=2)
    await pool.start()
    try:
        async def task(x):
            await asyncio.sleep(0.01)
            return x * 2

        out = await gather_with_pool(pool, [lambda i=i: task(i) for i in range(5)])
        assert sorted(out) == [0, 2, 4, 6, 8]
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pool_propagates_exception():
    pool = WorkerPool(max_concurrency=2)
    await pool.start()
    try:
        async def boom():
            raise ValueError("boom")

        with pytest.raises(ValueError):
            await pool.submit(boom())
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pool_priority_ordering():
    pool = WorkerPool(max_concurrency=1)
    await pool.start()
    order: list[str] = []
    try:
        async def t(name, delay):
            await asyncio.sleep(delay)
            order.append(name)
            return name

        first = asyncio.create_task(pool.submit(t("low-1", 0.0), priority="low"))
        await asyncio.sleep(0.005)
        asyncio.create_task(pool.submit(t("high-1", 0.0), priority="high"))
        asyncio.create_task(pool.submit(t("normal-1", 0.0), priority="normal"))
        await asyncio.sleep(0.05)
        await first
    finally:
        await pool.close()
    assert order[0] == "low-1"
    assert "high-1" in order and "normal-1" in order
    rest = order[1:]
    assert rest.index("high-1") < rest.index("normal-1")


@pytest.mark.asyncio
async def test_pool_respects_dynamic_concurrency():
    """Regression: AdaptiveRateController.current_concurrency must actually
    bound the number of in-flight tasks. Before the fix, _worker used a
    fixed asyncio.Semaphore(self._max) and current_concurrency was dead
    code (computed but never applied). This test forces a tight limit and
    asserts the pool honours it.
    """
    pool = WorkerPool(max_concurrency=8, latency_p95_threshold_ms=10_000_000)
    await pool.start()
    # Lock the rate controller so it cannot drift back up during the test:
    # under very low latency `observe_and_adjust()` would auto-increment.
    pool.rate.min_concurrency = 2
    pool.rate.max_concurrency = 2
    pool.rate.current_concurrency = 2

    in_flight = 0
    max_seen = 0
    seen_lock = asyncio.Lock()

    async def slow_task() -> int:
        nonlocal in_flight, max_seen
        async with seen_lock:
            in_flight += 1
            if in_flight > max_seen:
                max_seen = in_flight
        await asyncio.sleep(0.05)
        async with seen_lock:
            in_flight -= 1
        return 1

    try:
        out = await gather_with_pool(
            pool, [lambda: slow_task() for _ in range(20)]
        )
        assert sum(out) == 20
        assert max_seen <= 2, (
            f"current_concurrency=2 was set but {max_seen} tasks ran "
            "concurrently; the semaphore-vs-condvar fix is not in effect"
        )
    finally:
        await pool.close()


def test_rate_controller_halves_under_pressure():
    c = AdaptiveRateController(max_concurrency=8, latency_p95_threshold_ms=100, window=20)
    for _ in range(20):
        c.record(200)
    c.observe_and_adjust()
    assert c.current_concurrency <= 4


def test_rate_controller_recovers_under_calm():
    c = AdaptiveRateController(max_concurrency=8, latency_p95_threshold_ms=1000, window=20)
    c.current_concurrency = 2
    for _ in range(20):
        c.record(100)
    c.observe_and_adjust()
    assert c.current_concurrency == 3


def test_rate_controller_warmup_keeps_concurrency():
    c = AdaptiveRateController(max_concurrency=4, latency_p95_threshold_ms=10, window=20)
    c.record(99999)
    assert c.observe_and_adjust() == 4  # warmup: no change
