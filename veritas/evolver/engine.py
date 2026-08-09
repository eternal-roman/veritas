"""Public entry: run the evolutionary Idea engine and render reports."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from veritas.evolver.graph import build_runner
from veritas.evolver.llm import get_model
from veritas.evolver.state import AgentState


def initial_state(problem: str, *, model: Any | None = None) -> AgentState:
    state: AgentState = {
        "original_problem": problem,
        "first_principles": [],
        "system_constraints": [],
        "distant_paradigms": [],
        "population": [],
        "generation_count": 0,
        "best_solution": {},
        "final_architecture": "",
        "history": [],
    }
    if model is not None:
        state["_model"] = model  # type: ignore[typeddict-unknown-key]
    return state


def run_creativity_engine(
    problem: str,
    *,
    prefer_langgraph: bool = True,
    model: Any | None = None,
) -> AgentState:
    """Execute deconstruct → expand → explore → mutate/evaluate loop → orchestrate."""
    if model is None:
        model = get_model()
    state = initial_state(problem, model=model)
    runner = build_runner(prefer_langgraph=prefer_langgraph)
    return runner(state)


def render_idea_bus_section(state: AgentState) -> str:
    """Markdown fragment for IDEA_BUS — WATCH fuel, never approvals."""
    best = state.get("best_solution") or {}
    principles = state.get("first_principles") or []
    paradigms = state.get("distant_paradigms") or []
    lines = [
        "## Evolutionary synthesis (Evolver)",
        "",
        f"**Problem:** {state.get('original_problem', '')}",
        f"**Generations:** {state.get('generation_count', 0)}",
        f"**Best score (structural, not market):** {best.get('score', 0)}",
        "",
        "### First principles",
    ]
    for p in principles:
        lines.append(f"- {p}")
    lines += ["", "### Distant paradigms (WATCH)"]
    for p in paradigms:
        if isinstance(p, dict):
            lines.append(
                f"- **{p.get('domain')}** — {p.get('mechanism')} "
                f"→ transfer: {p.get('transfer')}"
            )
    lines += ["", "### Best recombinant blueprint (WATCH — not NEXT)"]
    lines.append(f"- id={best.get('id')} score={best.get('score')}")
    lines.append(f"- {best.get('blueprint')}")
    lines += ["", "### Architecture sketch"]
    lines.append(state.get("final_architecture") or "_(none)_")
    lines += [
        "",
        "### Banned claims",
        "- This section does **not** set STATE NEXT.",
        "- Seedlings/blueprints are **WATCH** hypotheses, not approvals.",
        "- Scores are structural heuristics, not commercial fitness.",
        "",
    ]
    return "\n".join(lines)


def write_report(state: AgentState, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
