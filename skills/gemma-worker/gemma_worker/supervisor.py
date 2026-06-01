from __future__ import annotations

import asyncio
import importlib
import json
import logging
import time
import uuid
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, ValidationError

from gemma_worker.client._shared import set_worker_context
from gemma_worker.client.base import Provider, WorkerConfig, build_client
from gemma_worker.queue.worker_pool import WorkerPool
from gemma_worker.store.sqlite_store import Store
from gemma_worker.tracer.otel_tracer import install_tracer

logger = logging.getLogger(__name__)

KNOWN_PLAYBOOKS = (
    "deadcode",
    "inconsistency",
    "gap",
    "research",
    "optimization",
    "synthesis",
    "critique",
    "devils_advocate",
    "steelman",
)


class WorkerState(TypedDict, total=False):
    task: str
    playbook: str
    priority: str
    iterations: int
    max_iterations: int
    artifacts: list[dict[str, Any]]
    reflexion_history: list[str]
    audit_layer_0: list[dict[str, Any]]
    audit_layer_2: list[dict[str, Any]]
    metrics: dict[str, Any]
    verdict: Literal["PROMOTE", "HOLD", "ROLLBACK"] | None
    trace_id: str
    task_id: str
    error: str | None
    last_started_at: float
    elapsed_ms_per_iter: list[int]


class WorkerStateValidator(BaseModel):
    model_config = ConfigDict(extra="allow")

    task: str
    playbook: str
    priority: Literal["high", "normal", "low"] = "normal"
    iterations: int = 0
    max_iterations: int = 3
    artifacts: list[dict[str, Any]] = []
    reflexion_history: list[str] = []
    audit_layer_0: list[dict[str, Any]] = []
    audit_layer_2: list[dict[str, Any]] = []
    metrics: dict[str, Any] = {}
    verdict: Literal["PROMOTE", "HOLD", "ROLLBACK"] | None = None
    trace_id: str = ""
    task_id: str = ""
    error: str | None = None
    last_started_at: float = 0.0
    elapsed_ms_per_iter: list[int] = []


def _validate_state(state: WorkerState, *, node: str) -> WorkerState:
    try:
        WorkerStateValidator.model_validate(state)
    except ValidationError as e:
        raise RuntimeError(f"checkpoint validation failed at node {node!r}: {e}") from e
    return state


_PLAYBOOK_MODULES = {name: f"gemma_worker.playbooks.{name}" for name in KNOWN_PLAYBOOKS}


def _load_playbook(name: str):
    mod_path = _PLAYBOOK_MODULES.get(name)
    if not mod_path:
        raise ValueError(f"unknown playbook: {name!r}")
    mod = importlib.import_module(mod_path)
    if not hasattr(mod, "run"):
        raise RuntimeError(f"playbook {name} missing run()")
    return mod.run


async def _route(state: WorkerState, *, client: Provider) -> WorkerState:
    if state.get("playbook") and state["playbook"] != "auto":
        return state
    classification_prompt = (
        "Classify the following development task into exactly one of these playbooks:\n"
        f"{', '.join(KNOWN_PLAYBOOKS)}.\n\n"
        f"Task: {state['task']}\n\n"
        'Return JSON: {"playbook": "<one of the names above>"}'
    )
    result = await client.call(
        system="You are a strict task classifier. Output JSON only.",
        user=classification_prompt,
        want_json=True,
    )
    chosen = "synthesis"
    if result.status == "ok" and isinstance(result.json, dict):
        candidate = str(result.json.get("playbook", "")).lower()
        if candidate in KNOWN_PLAYBOOKS:
            chosen = candidate
    state["playbook"] = chosen
    return state


async def _execute_playbook(state: WorkerState, *, client: Provider, pool: WorkerPool,
                            store: Store) -> WorkerState:
    state["last_started_at"] = time.perf_counter()
    playbook_run = _load_playbook(state["playbook"])
    try:
        artifacts = await playbook_run(
            task=state["task"],
            client=client,
            pool=pool,
            store=store,
            reflexion=state.get("reflexion_history", []),
        )
    except Exception as e:
        state["error"] = f"{type(e).__name__}: {e}"
        return state
    state.setdefault("artifacts", []).extend(artifacts or [])
    elapsed_ms = int((time.perf_counter() - state["last_started_at"]) * 1000)
    state.setdefault("elapsed_ms_per_iter", []).append(elapsed_ms)
    return state


async def _audit_layer_0(state: WorkerState, *, store: Store) -> WorkerState:
    state["audit_layer_0"] = state.get("audit_layer_0", [])
    return state


async def _measure(state: WorkerState, *, store: Store) -> WorkerState:
    from gemma_worker.gate.runtime_gate import compute_metrics, to_verdict

    spans = await store.list_spans(state["trace_id"]) if state.get("trace_id") else []
    metrics = compute_metrics(
        artifacts=state.get("artifacts", []),
        spans=spans,
        elapsed_ms_per_iter=state.get("elapsed_ms_per_iter", []),
        audit_layer_2=state.get("audit_layer_2", []),
    )
    state["metrics"] = metrics
    state["verdict"] = to_verdict(metrics)
    return state


async def _reflect(state: WorkerState, *, client: Provider) -> WorkerState:
    iters = state.get("iterations", 0)
    state["iterations"] = iters + 1
    history = state.setdefault("reflexion_history", [])
    metrics = state.get("metrics", {})
    artifacts = state.get("artifacts", [])
    summary = (
        f"Iteration {state['iterations']} produced verdict={state.get('verdict')} "
        f"with metrics={json.dumps(metrics, ensure_ascii=False)}. "
        f"Last artifacts count: {len(artifacts)}."
    )
    history.append(summary)
    prompt = (
        f"Original task: {state['task']}\n"
        f"Current verdict: {state.get('verdict')}\n"
        f"Metrics: {json.dumps(metrics, ensure_ascii=False)}\n"
        f"Recent reflexion history:\n- " + "\n- ".join(history[-3:]) + "\n\n"
        'In ONE sentence, state the most important adjustment for the next attempt. '
        'Return JSON: {"adjustment": "..."}'
    )
    result = await client.call(
        system="You are a self-critic. Be concise. Output JSON.",
        user=prompt,
        want_json=True,
    )
    if result.status == "ok" and isinstance(result.json, dict):
        adj = result.json.get("adjustment")
        if adj:
            history.append(f"Adjustment: {adj}")
    return state


def _should_continue(state: WorkerState) -> Literal["reflect", "end"]:
    verdict = state.get("verdict")
    iters = state.get("iterations", 0)
    max_iters = state.get("max_iterations", 3)
    if verdict in ("PROMOTE", "ROLLBACK"):
        return "end"
    if iters >= max_iters:
        return "end"
    return "reflect"


def build_graph(*, client: Provider, pool: WorkerPool, store: Store):
    async def route_node(s: WorkerState) -> WorkerState:
        return _validate_state(await _route(s, client=client), node="route")

    async def execute_node(s: WorkerState) -> WorkerState:
        return _validate_state(
            await _execute_playbook(s, client=client, pool=pool, store=store),
            node="execute",
        )

    async def audit_node(s: WorkerState) -> WorkerState:
        return _validate_state(await _audit_layer_0(s, store=store), node="audit")

    async def measure_node(s: WorkerState) -> WorkerState:
        return _validate_state(await _measure(s, store=store), node="measure")

    async def reflect_node(s: WorkerState) -> WorkerState:
        return _validate_state(await _reflect(s, client=client), node="reflect")

    g: StateGraph = StateGraph(WorkerState)
    g.add_node("route", route_node)
    g.add_node("execute", execute_node)
    g.add_node("audit", audit_node)
    g.add_node("measure", measure_node)
    g.add_node("reflect", reflect_node)
    g.add_edge(START, "route")
    g.add_edge("route", "execute")
    g.add_edge("execute", "audit")
    g.add_edge("audit", "measure")
    g.add_conditional_edges(
        "measure",
        _should_continue,
        {"reflect": "reflect", "end": END},
    )
    g.add_edge("reflect", "execute")
    return g.compile()


async def run_supervisor(
    *,
    task: str,
    playbook: str = "auto",
    max_iterations: int = 3,
    priority: str = "normal",
    config: WorkerConfig | None = None,
) -> dict[str, Any]:
    cfg = config or WorkerConfig.from_env()
    store = Store()
    await store.init()
    install_tracer(store)
    client = build_client(cfg)

    # Set the worker context BEFORE spawning the pool's worker tasks. The
    # worker context lives in ContextVars, and asyncio.create_task() snapshots
    # the current context at task-creation time. If we set the context after
    # pool.start(), workers see the default (None) and their spans cannot be
    # correlated to this supervisor run.
    task_id = uuid.uuid4().hex
    trace_id = uuid.uuid4().hex
    set_worker_context(trace_id=trace_id, task_id=task_id)

    pool = WorkerPool()
    await pool.start()

    await store.start_trace(
        trace_id=trace_id, task_id=task_id, playbook=playbook,
        payload={"task": task},
    )

    initial: WorkerState = {
        "task": task,
        "playbook": playbook,
        "priority": priority,
        "iterations": 0,
        "max_iterations": max_iterations,
        "artifacts": [],
        "reflexion_history": [],
        "audit_layer_0": [],
        "audit_layer_2": [],
        "trace_id": trace_id,
        "task_id": task_id,
        "elapsed_ms_per_iter": [],
    }

    graph = build_graph(client=client, pool=pool, store=store)
    try:
        final = await graph.ainvoke(initial)
    finally:
        await pool.close()
        try:
            from opentelemetry import trace as _trace
            provider = _trace.get_tracer_provider()
            if hasattr(provider, "force_flush"):
                provider.force_flush(timeout_millis=5000)
        except Exception:
            pass

    verdict = final.get("verdict") or "HOLD"
    from gemma_worker.gate.runtime_gate import split_findings_and_escalations

    all_artifacts = final.get("artifacts", [])
    findings, escalations = split_findings_and_escalations(all_artifacts)
    out = {
        "verdict": verdict,
        "metrics": final.get("metrics", {}),
        "artifacts": findings,
        "escalations": escalations,
        "trace_id": trace_id,
        "task_id": task_id,
        "iterations": final.get("iterations", 0),
        "reflexion_history": final.get("reflexion_history", []),
        "playbook": final.get("playbook"),
        "audit": {
            "axes_1_to_4": final.get("audit_layer_0", []),
            "axes_5_to_6": final.get("audit_layer_2", []),
        },
        "error": final.get("error"),
    }
    await store.finish_trace(trace_id=trace_id, verdict=verdict, payload=out)
    return out
