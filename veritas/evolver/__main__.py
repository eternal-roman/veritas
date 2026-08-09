"""CLI: evolve problems and run the roadblock→origin journal workflow."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from veritas.evolver.engine import (
    render_idea_bus_section,
    run_creativity_engine,
    write_report,
)
from veritas.evolver.journal import ProblemJournal, seed_progress_blockers
from veritas.evolver.workflow import run_full_cycle, run_tick


def _print(obj: object) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def cmd_evolve(args: argparse.Namespace) -> int:
    if args.problem_file:
        problem = args.problem_file.read_text(encoding="utf-8").strip()
    elif getattr(args, "problem", None):
        problem = args.problem.strip()
    else:
        print("error: provide problem text or --problem-file", file=sys.stderr)
        return 2
    state = run_creativity_engine(problem, prefer_langgraph=not getattr(args, "no_langgraph", False))
    if getattr(args, "json_out", None):
        write_report(state, args.json_out)
    if getattr(args, "idea_bus_out", None):
        args.idea_bus_out.parent.mkdir(parents=True, exist_ok=True)
        args.idea_bus_out.write_text(render_idea_bus_section(state), encoding="utf-8")
    if getattr(args, "print_bus", False):
        print(render_idea_bus_section(state))
    else:
        _print({
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
        })
    return 0


def cmd_submit(args: argparse.Namespace) -> int:
    j = ProblemJournal(args.journal)
    p = j.submit(
        args.sender, args.title, args.detail or "",
        kind=args.kind, severity=args.severity,
        sender_role=args.role or args.sender,
        source_surface=args.source or "",
        correlation_id=args.correlation or "",
    )
    j.close()
    _print(p.to_dict())
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    j = ProblemJournal(args.journal)
    if args.sender:
        rows = [p.to_dict() for p in j.list_for_sender(args.sender)]
    else:
        rows = [p.to_dict() for p in j.list_open(limit=args.limit)]
    j.close()
    _print({"count": len(rows), "problems": rows})
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    j = ProblemJournal(args.journal)
    snap = j.snapshot()
    j.close()
    _print(snap)
    return 0


def cmd_seed(args: argparse.Namespace) -> int:
    j = ProblemJournal(args.journal)
    seeded = seed_progress_blockers(j)
    snap = j.snapshot()
    j.close()
    _print({"seeded": [p.problem_id for p in seeded], "journal": snap})
    return 0


def cmd_tick(args: argparse.Namespace) -> int:
    out = run_tick(
        max_cycles=args.max_cycles,
        seed=not args.no_seed,
        prefer_langgraph=bool(getattr(args, "prefer_langgraph", False)),
        evolver_id=args.evolver_id,
        artifact_root=Path(args.artifact_root) if args.artifact_root else None,
    )
    _print(out)
    return 0


def cmd_cycle(args: argparse.Namespace) -> int:
    j = ProblemJournal(args.journal)
    p = j.get(args.problem_id)
    if p.status == "open":
        p = j.claim(p.problem_id, args.evolver_id)
    out = run_full_cycle(
        p, j,
        artifact_root=Path(args.artifact_root) if args.artifact_root else None,
        evolver_id=args.evolver_id,
        prefer_langgraph=bool(getattr(args, "prefer_langgraph", False)),
    )
    j.close()
    _print(out)
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="veritas-evolver",
        description="Evolutionary Idea engine + roadblock journal. WATCH only.",
    )
    p.add_argument("--journal", default=None, help="Path to evolver_journal.sqlite3")
    sub = p.add_subparsers(dest="command")

    s = sub.add_parser("submit", help="Origin agent journals a roadblock/concern")
    s.add_argument("--sender", required=True, help="Origin agent id (required)")
    s.add_argument("--role", default="")
    s.add_argument("--title", required=True)
    s.add_argument("--detail", default="")
    s.add_argument("--kind", default="block",
                   choices=["block","concern","issue","stall","strategy","money_egress","technical","general"])
    s.add_argument("--severity", type=int, default=2)
    s.add_argument("--source", default="")
    s.add_argument("--correlation", default="")
    s.set_defaults(func=cmd_submit)

    s = sub.add_parser("list", help="List open problems (or by sender)")
    s.add_argument("--sender", default="")
    s.add_argument("--limit", type=int, default=20)
    s.set_defaults(func=cmd_list)

    s = sub.add_parser("snapshot", help="Journal counts + open queue")
    s.set_defaults(func=cmd_snapshot)

    s = sub.add_parser("seed", help="Seed steady progress-blocker supply")
    s.set_defaults(func=cmd_seed)

    s = sub.add_parser("tick", help="Seed + claim + full cycle (origin/overseer/eng)")
    s.add_argument("--max-cycles", type=int, default=1)
    s.add_argument("--no-seed", action="store_true")
    s.add_argument("--evolver-id", default="evolver")
    s.add_argument("--artifact-root", default=None)
    s.add_argument("--prefer-langgraph", action="store_true")
    s.set_defaults(func=cmd_tick)

    s = sub.add_parser("cycle", help="Full roadblock→origin workflow for one id")
    s.add_argument("problem_id")
    s.add_argument("--evolver-id", default="evolver")
    s.add_argument("--artifact-root", default=None)
    s.add_argument("--prefer-langgraph", action="store_true")
    s.set_defaults(func=cmd_cycle)

    s = sub.add_parser("evolve", help="Run evolutionary engine only (no journal)")
    s.add_argument("problem", nargs="?", default=None)
    s.add_argument("--problem-file", type=Path, default=None)
    s.add_argument("--json-out", type=Path, default=None)
    s.add_argument("--idea-bus-out", type=Path, default=None)
    s.add_argument("--no-langgraph", action="store_true")
    s.add_argument("--print-bus", action="store_true")
    s.set_defaults(func=cmd_evolve)

    return p


def main(argv: list[str] | None = None) -> int:
    raw = list(sys.argv[1:] if argv is None else argv)
    known = {"submit", "list", "snapshot", "seed", "tick", "cycle", "evolve", "-h", "--help"}
    # Legacy: veritas-evolver "problem text" … → evolve subcommand
    if raw and raw[0] not in known and not raw[0].startswith("-"):
        raw = ["evolve", *raw]
    elif raw and raw[0].startswith("-") and not any(
        a in known for a in raw if not a.startswith("-")
    ):
        # flags-only with --problem-file etc.
        if any(a in ("--problem-file", "--print-bus", "--json-out") for a in raw):
            raw = ["evolve", *raw]

    parser = build_parser()
    args = parser.parse_args(raw)
    if getattr(args, "func", None):
        return int(args.func(args))
    if getattr(args, "problem", None) or getattr(args, "problem_file", None):
        return cmd_evolve(args)
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
