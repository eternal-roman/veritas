"""CLI: python -m veritas.evolver \"problem statement\""""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from veritas.evolver.engine import (
    render_idea_bus_section,
    run_creativity_engine,
    write_report,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="veritas-evolver",
        description=(
            "Evolutionary Idea engine (Evolver). Produces WATCH fuel only — "
            "never sets STATE NEXT. Default model is offline/deterministic."
        ),
    )
    parser.add_argument(
        "problem",
        nargs="?",
        default=None,
        help="Problem statement to evolve (or pass --problem-file).",
    )
    parser.add_argument(
        "--problem-file",
        type=Path,
        default=None,
        help="Read problem text from a file.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Write full AgentState JSON to this path.",
    )
    parser.add_argument(
        "--idea-bus-out",
        type=Path,
        default=None,
        help="Write IDEA_BUS markdown section to this path.",
    )
    parser.add_argument(
        "--no-langgraph",
        action="store_true",
        help="Force pure-Python graph (skip LangGraph even if installed).",
    )
    parser.add_argument(
        "--print-bus",
        action="store_true",
        help="Print IDEA_BUS section to stdout instead of full JSON state.",
    )
    args = parser.parse_args(argv)

    if args.problem_file:
        problem = args.problem_file.read_text(encoding="utf-8").strip()
    elif args.problem:
        problem = args.problem.strip()
    else:
        parser.error("provide problem text or --problem-file")
        return 2

    state = run_creativity_engine(
        problem,
        prefer_langgraph=not args.no_langgraph,
    )

    if args.json_out:
        write_report(state, args.json_out)
    if args.idea_bus_out:
        args.idea_bus_out.parent.mkdir(parents=True, exist_ok=True)
        args.idea_bus_out.write_text(render_idea_bus_section(state), encoding="utf-8")

    if args.print_bus:
        print(render_idea_bus_section(state))
    else:
        # Compact summary JSON for agents
        summary = {
            "schema": "veritas.evolver.v0",
            "generations": state.get("generation_count"),
            "best_score": (state.get("best_solution") or {}).get("score"),
            "best_blueprint": (state.get("best_solution") or {}).get("blueprint"),
            "first_principles": state.get("first_principles"),
            "paradigms": [
                p.get("domain") if isinstance(p, dict) else p
                for p in (state.get("distant_paradigms") or [])
            ],
            "not_state_next": True,
            "watch_only": True,
        }
        print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
