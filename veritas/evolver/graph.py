"""Evolutionary state machine — LangGraph when installed, pure Python fallback."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from veritas.evolver.agents import (
    deconstructor_node,
    explorer_node,
    mutator_node,
    orchestrator_node,
    reasoning_node,
    validator_node,
)
from veritas.evolver.state import AgentState

SCORE_THRESHOLD = 0.90
MAX_GENERATIONS = 5


def evolution_check(state: AgentState) -> str:
    best_score = float((state.get("best_solution") or {}).get("score") or 0.0)
    generations = int(state.get("generation_count") or 0)
    if best_score >= SCORE_THRESHOLD or generations >= MAX_GENERATIONS:
        return "orchestrate"
    return "mutate"


def _merge(state: AgentState, update: dict[str, Any]) -> AgentState:
    out: dict[str, Any] = dict(state)
    hist = list(out.get("history") or [])
    for k, v in update.items():
        if k == "history" and isinstance(v, list):
            hist.extend(v)
        else:
            out[k] = v
    out["history"] = hist
    return out  # type: ignore[return-value]


def run_pure(state: AgentState) -> AgentState:
    """Deterministic graph without LangGraph dependency."""
    s = _merge(state, deconstructor_node(state))
    s = _merge(s, reasoning_node(s))
    s = _merge(s, explorer_node(s))
    # Initial mutate seeds population
    s = _merge(s, mutator_node(s))
    s = _merge(s, validator_node(s))
    while evolution_check(s) == "mutate":
        s = _merge(s, mutator_node(s))
        s = _merge(s, validator_node(s))
    s = _merge(s, orchestrator_node(s))
    return s


def build_langgraph():
    """Compile a LangGraph app that executes the pure multi-node loop.

    The multi-node topology (deconstruct → expand → explore → mutate ⇄ evaluate
    → orchestrate) is implemented in :func:`run_pure` so scores, generation
    caps, and offline models stay deterministic in CI. LangGraph provides the
    installable orchestration surface required by the evolutionary directive;
    multi-node channel wiring for bare ``dict`` state is unstable across LG
    versions, so the graph entry is a single honest ``evolve`` node.
    """
    from langgraph.graph import END, StateGraph

    workflow = StateGraph(dict)

    def evolve(state: dict[str, Any]) -> dict[str, Any]:
        return dict(run_pure(state))  # type: ignore[arg-type]

    workflow.add_node("evolve", evolve)
    workflow.set_entry_point("evolve")
    workflow.add_edge("evolve", END)
    return workflow.compile()


def build_runner(*, prefer_langgraph: bool = True) -> Callable[[AgentState], AgentState]:
    """Return a state runner.

    Pure-Python multi-node graph is **canonical** (CI + offline ticks).
    When LangGraph is installed and preferred, invoke through the LG wrapper.
    """
    if prefer_langgraph:
        try:
            app = build_langgraph()

            def _run(state: AgentState) -> AgentState:
                result = app.invoke(dict(state))
                if not result.get("first_principles") and not result.get(
                    "generation_count"
                ):
                    return run_pure(state)
                return result  # type: ignore[return-value]

            return _run
        except ImportError:
            pass
    return run_pure
