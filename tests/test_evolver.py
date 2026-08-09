"""Evolver evolutionary Idea engine — offline graph honesty."""

from __future__ import annotations

import json

from veritas.evolver.engine import render_idea_bus_section, run_creativity_engine
from veritas.evolver.graph import MAX_GENERATIONS, evolution_check, run_pure
from veritas.evolver.llm import OfflineEvolutionaryModel
from veritas.evolver.state import AgentState


def test_pure_loop_terminates_and_orchestrates() -> None:
    problem = "Scale agent-to-agent commerce trust without dual payment paths"
    state = run_creativity_engine(
        problem,
        prefer_langgraph=False,
        model=OfflineEvolutionaryModel(),
    )
    assert state["generation_count"] >= 1
    assert state["generation_count"] <= MAX_GENERATIONS
    assert state["first_principles"]
    assert len(state["distant_paradigms"]) >= 1
    assert state["best_solution"].get("blueprint")
    assert float(state["best_solution"].get("score") or 0) >= 0
    assert "execution" in state["final_architecture"].lower() or "DAG" in state[
        "final_architecture"
    ] or "Stage-1" in state["final_architecture"]
    # Terminal condition must hold
    assert evolution_check(state) == "orchestrate"


def test_evolution_check_routes_by_score_and_gens() -> None:
    low: AgentState = {
        "best_solution": {"score": 0.1},
        "generation_count": 1,
    }
    assert evolution_check(low) == "mutate"
    high: AgentState = {
        "best_solution": {"score": 0.95},
        "generation_count": 1,
    }
    assert evolution_check(high) == "orchestrate"
    maxed: AgentState = {
        "best_solution": {"score": 0.1},
        "generation_count": MAX_GENERATIONS,
    }
    assert evolution_check(maxed) == "orchestrate"


def test_idea_bus_section_is_watch_only() -> None:
    state = run_pure(
        {
            "original_problem": "test problem",
            "first_principles": [],
            "system_constraints": [],
            "distant_paradigms": [],
            "population": [],
            "generation_count": 0,
            "best_solution": {},
            "final_architecture": "",
            "history": [],
            "_model": OfflineEvolutionaryModel(),  # type: ignore[typeddict-item]
        }
    )
    md = render_idea_bus_section(state)
    assert "WATCH" in md
    assert "not set STATE NEXT" in md or "does **not** set STATE NEXT" in md
    assert "Evolutionary synthesis" in md


def test_cli_main_offline(tmp_path, capsys) -> None:
    from veritas.evolver.__main__ import main

    out = tmp_path / "state.json"
    bus = tmp_path / "bus.md"
    code = main(
        [
            "Reduce verification latency for stranger agents",
            "--no-langgraph",
            "--json-out",
            str(out),
            "--idea-bus-out",
            str(bus),
        ]
    )
    assert code == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema"] == "veritas.evolver.v0"
    assert summary["watch_only"] is True
    assert summary["not_state_next"] is True
    assert out.is_file()
    assert "WATCH" in bus.read_text(encoding="utf-8")
