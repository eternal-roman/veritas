"""Node functions for the evolutionary Idea ensemble."""

from __future__ import annotations

import re
from typing import Any

from veritas.evolver.llm import ChatModel, OfflineEvolutionaryModel, parse_json_response
from veritas.evolver.prompts import (
    DECONSTRUCTOR_PROMPT,
    EXPLORER_PROMPT,
    MUTATOR_PROMPT,
    ORCHESTRATOR_PROMPT,
    REASONING_PROMPT,
)
from veritas.evolver.state import AgentState


def _model(state: AgentState) -> ChatModel:
    # Allow tests to inject via state under private key (not in TypedDict schema export).
    injected = state.get("_model")  # type: ignore[assignment]
    if injected is not None:
        return injected  # type: ignore[return-value]
    return OfflineEvolutionaryModel()


def deconstructor_node(state: AgentState) -> dict[str, Any]:
    problem = state.get("original_problem") or ""
    raw = _model(state).complete(
        DECONSTRUCTOR_PROMPT.split("Problem:")[0].strip(),
        DECONSTRUCTOR_PROMPT.format(problem=problem),
    )
    principles = parse_json_response(raw, expect=list)
    principles = [str(p) for p in principles if str(p).strip()][:5]
    if len(principles) < 3:
        principles = OfflineEvolutionaryModel().complete(
            "First Principles Engine deconstructive reduction",
            f"Problem:\n{problem}",
        )
        principles = parse_json_response(principles, expect=list)
        principles = [str(p) for p in principles][:5]
    return {
        "first_principles": principles,
        "history": [{"node": "deconstruct", "n": len(principles)}],
    }


def reasoning_node(state: AgentState) -> dict[str, Any]:
    principles = state.get("first_principles") or []
    problem = state.get("original_problem") or ""
    raw = _model(state).complete(
        "You are the Constraints Mapper.",
        REASONING_PROMPT.format(
            principles=json_dumps(principles),
            problem=problem,
        ),
    )
    constraints = [str(c) for c in parse_json_response(raw, expect=list) if str(c).strip()]
    if not constraints:
        constraints = [
            "Single money path",
            "Fail closed on outage",
            "WATCH not approve for idea fuel",
        ]
    return {
        "system_constraints": constraints[:6],
        "history": [{"node": "expand", "n": len(constraints)}],
    }


def explorer_node(state: AgentState) -> dict[str, Any]:
    principles = state.get("first_principles") or []
    constraints = state.get("system_constraints") or []
    raw = _model(state).complete(
        "You are the Recombinant Search Engine.",
        EXPLORER_PROMPT.format(
            principles=json_dumps(principles),
            constraints=json_dumps(constraints),
        ),
    )
    paradigms = parse_json_response(raw, expect=list)
    cleaned: list[dict[str, Any]] = []
    for p in paradigms:
        if isinstance(p, dict) and p.get("domain"):
            cleaned.append(
                {
                    "domain": str(p.get("domain")),
                    "mechanism": str(p.get("mechanism") or ""),
                    "transfer": str(p.get("transfer") or ""),
                }
            )
    if len(cleaned) < 3:
        fallback = OfflineEvolutionaryModel().complete(
            "Recombinant Search Engine",
            "principles",
        )
        cleaned = parse_json_response(fallback, expect=list)
    return {
        "distant_paradigms": cleaned[:3],
        "history": [{"node": "explore", "n": len(cleaned[:3])}],
    }


def mutator_node(state: AgentState) -> dict[str, Any]:
    gen = int(state.get("generation_count") or 0)
    next_gen = gen + 1
    principles = state.get("first_principles") or []
    paradigms = state.get("distant_paradigms") or []
    population = list(state.get("population") or [])
    best = sorted(population, key=lambda x: float(x.get("score") or 0), reverse=True)[:2]
    if not best and state.get("best_solution"):
        best = [state["best_solution"]]

    raw = _model(state).complete(
        "You are the Evolutionary Mutator.",
        MUTATOR_PROMPT.format(
            principles=json_dumps(principles),
            paradigms=json_dumps(paradigms),
            gen=next_gen,
            best_candidates=json_dumps(best),
        ),
    )
    mutants = parse_json_response(raw, expect=list)
    new_pop: list[dict[str, Any]] = []
    base_id = max([int(m.get("id") or 0) for m in population] + [0])
    for m in mutants:
        if not isinstance(m, dict):
            continue
        blueprint = str(m.get("blueprint") or "").strip()
        if not blueprint:
            continue
        base_id += 1
        new_pop.append(
            {
                "id": base_id,
                "blueprint": blueprint,
                "score": 0.0,
                "generation": next_gen,
                "paradigm_ids": list(m.get("paradigm_ids") or []),
                "rationale": str(m.get("rationale") or ""),
            }
        )
    if not new_pop:
        # Structural fallback from paradigms alone.
        for i, p in enumerate(paradigms[:3]):
            base_id += 1
            domain = p.get("domain") if isinstance(p, dict) else f"p{i}"
            transfer = p.get("transfer") if isinstance(p, dict) else ""
            new_pop.append(
                {
                    "id": base_id,
                    "blueprint": f"Gen{next_gen}: apply {domain} — {transfer}",
                    "score": 0.0,
                    "generation": next_gen,
                    "paradigm_ids": [str(domain)],
                }
            )

    # Keep elites + new mutants
    elites = best[:2]
    merged = elites + new_pop
    return {
        "generation_count": next_gen,
        "population": merged,
        "history": [{"node": "mutate", "gen": next_gen, "n": len(new_pop)}],
    }


def validator_node(state: AgentState) -> dict[str, Any]:
    """Programmatic scoring — never invents market fitness."""
    principles = [str(p).lower() for p in (state.get("first_principles") or [])]
    constraints = [str(c).lower() for c in (state.get("system_constraints") or [])]
    population = list(state.get("population") or [])
    scored: list[dict[str, Any]] = []

    for member in population:
        text = str(member.get("blueprint") or "").lower()
        if not text:
            continue
        p_hits = sum(1 for p in principles if _overlap(p, text))
        c_hits = sum(1 for c in constraints if _overlap(c, text))
        novelty = 0.2 if member.get("paradigm_ids") else 0.05
        concrete = 0.1 if any(
            k in text for k in ("test", "accept", "ledger", "hash", "sdk", "api", "cli")
        ) else 0.02
        score = min(
            1.0,
            0.15
            + 0.4 * (p_hits / max(1, len(principles)))
            + 0.3 * (c_hits / max(1, len(constraints)))
            + novelty
            + concrete
            + 0.05 * min(3, int(member.get("generation") or 0)),
        )
        row = dict(member)
        row["score"] = round(score, 4)
        scored.append(row)

    scored.sort(key=lambda x: float(x.get("score") or 0), reverse=True)
    best = scored[0] if scored else {
        "id": 0,
        "blueprint": "no_viable_candidate",
        "score": 0.0,
        "generation": int(state.get("generation_count") or 0),
    }
    return {
        "population": scored,
        "best_solution": best,
        "history": [
            {
                "node": "evaluate",
                "best_score": best.get("score"),
                "best_id": best.get("id"),
            }
        ],
    }


def orchestrator_node(state: AgentState) -> dict[str, Any]:
    best = state.get("best_solution") or {}
    problem = state.get("original_problem") or ""
    raw = _model(state).complete(
        "You are the Lead Systems Architect (Idea fuel only).",
        ORCHESTRATOR_PROMPT.format(
            best_solution=json_dumps(best),
            problem=problem,
        ),
    )
    arch = raw.strip() if raw.strip() else "# No architecture produced\n"
    return {
        "final_architecture": arch,
        "history": [{"node": "orchestrate", "chars": len(arch)}],
    }


def _overlap(needle: str, hay: str) -> bool:
    needle = needle.strip()
    if len(needle) < 4:
        return False
    # Wordish tokens from principle
    tokens = [t for t in re.split(r"[^a-z0-9]+", needle) if len(t) >= 5]
    if not tokens:
        return needle[:20] in hay
    return sum(1 for t in tokens if t in hay) >= max(1, len(tokens) // 3)


def json_dumps(obj: Any) -> str:
    import json

    return json.dumps(obj, indent=2, sort_keys=True, default=str)
