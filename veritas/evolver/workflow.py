"""Full roadblock → Evolver → origin mapping runner."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from veritas.evolver.engine import render_idea_bus_section, run_creativity_engine
from veritas.evolver.journal import (
    Problem,
    ProblemJournal,
    default_artifact_root,
    seed_progress_blockers,
    workflow_phase,
)
from veritas.evolver.llm import OfflineEvolutionaryModel, get_model


def run_full_cycle(
    problem: Problem,
    journal: ProblemJournal,
    *,
    artifact_root: Path | None = None,
    evolver_id: str = "evolver",
    prefer_langgraph: bool = False,
    model: Any | None = None,
) -> dict[str, Any]:
    root = artifact_root or default_artifact_root()
    root.mkdir(parents=True, exist_ok=True)
    runs = root / "runs"
    runs.mkdir(parents=True, exist_ok=True)

    p = journal.get(problem.problem_id)
    if p.status == "open":
        p = journal.claim(p.problem_id, evolver_id)
    elif p.status != "evolving":
        return _resume_reports(journal, p, root)

    prompt = (
        f"Origin agent: {p.sender_agent} (role {p.sender_role or p.sender_agent})\n"
        f"Kind: {p.kind} severity={p.severity}\n"
        f"Source: {p.source_surface}\n"
        f"Title: {p.title}\n\n"
        f"{p.detail}"
    )
    if model is None:
        model = get_model()
    state = run_creativity_engine(
        prompt, prefer_langgraph=prefer_langgraph, model=model,
    )
    best = state.get("best_solution") or {}
    blueprint = str(best.get("blueprint") or "no_blueprint")
    score = float(best.get("score") or 0.0)

    json_path = runs / f"{p.problem_id}.json"
    payload = {
        "schema": "veritas.evolver.run.v0",
        "problem": p.to_dict(),
        "state": {
            "generation_count": state.get("generation_count"),
            "first_principles": state.get("first_principles"),
            "system_constraints": state.get("system_constraints"),
            "distant_paradigms": state.get("distant_paradigms"),
            "best_solution": best,
            "final_architecture": state.get("final_architecture"),
        },
        "idea_bus_section": render_idea_bus_section(state),
        "not_state_next": True,
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")

    p = journal.attach_synthesis(
        p.problem_id,
        best_blueprint=blueprint,
        best_score=score,
        synthesis_json_path=str(json_path),
    )
    p = journal.report_to_origin(p.problem_id, artifact_root=root)
    p = journal.report_to_overseer(p.problem_id, artifact_root=root)
    p = journal.handoff_engineering(p.problem_id, artifact_root=root)

    return {
        "schema": "veritas.evolver.workflow.v0",
        "problem": p.to_dict(),
        "workflow_phase": workflow_phase(p.status),
        "paths": {
            "synthesis_json": p.synthesis_json_path,
            "origin_report": p.origin_report_path,
            "overseer_report": p.overseer_report_path,
            "engineering_report": p.engineering_report_path,
        },
        "mapped_to_origin": p.sender_agent,
        "not_state_next": True,
    }


def _resume_reports(journal: ProblemJournal, p: Problem, root: Path) -> dict[str, Any]:
    if p.status == "synthesized":
        p = journal.report_to_origin(p.problem_id, artifact_root=root)
        p = journal.report_to_overseer(p.problem_id, artifact_root=root)
        p = journal.handoff_engineering(p.problem_id, artifact_root=root)
    elif p.status == "reported_origin":
        p = journal.report_to_overseer(p.problem_id, artifact_root=root)
        p = journal.handoff_engineering(p.problem_id, artifact_root=root)
    elif p.status == "overseer_queued":
        p = journal.handoff_engineering(p.problem_id, artifact_root=root)
    return {
        "schema": "veritas.evolver.workflow.v0",
        "problem": p.to_dict(),
        "workflow_phase": workflow_phase(p.status),
        "paths": {
            "synthesis_json": p.synthesis_json_path,
            "origin_report": p.origin_report_path,
            "overseer_report": p.overseer_report_path,
            "engineering_report": p.engineering_report_path,
        },
        "mapped_to_origin": p.sender_agent,
        "resumed": True,
        "not_state_next": True,
    }


def run_tick(
    *,
    base_dir: Path | str | None = None,
    artifact_root: Path | None = None,
    evolver_id: str = "evolver",
    max_cycles: int = 1,
    seed: bool = True,
    prefer_langgraph: bool = False,
) -> dict[str, Any]:
    base = Path(base_dir) if base_dir else Path.cwd() / ".veritas"
    base.mkdir(parents=True, exist_ok=True)
    journal = ProblemJournal(base / "evolver_journal.sqlite3")
    root = artifact_root or default_artifact_root()
    seeded: list[str] = []
    if seed:
        seeded = [p.problem_id for p in seed_progress_blockers(journal)]

    acted: list[dict[str, Any]] = []
    for _ in range(max(1, max_cycles)):
        nxt = journal.claim_next(evolver_id)
        if nxt is None:
            break
        result = run_full_cycle(
            nxt, journal, artifact_root=root, evolver_id=evolver_id,
            prefer_langgraph=prefer_langgraph, model=OfflineEvolutionaryModel(),
        )
        acted.append(result)

    snap = journal.snapshot()
    journal.close()
    return {
        "schema": "veritas.evolver.tick.v0",
        "evolver_id": evolver_id,
        "ts": time.time(),
        "seeded": seeded,
        "acted": acted,
        "journal": snap,
        "not_state_next": True,
    }
