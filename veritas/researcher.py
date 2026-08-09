"""Autonomous Researcher — see blocks, research, solve when local, report back.

Run one tick: ``python -m veritas.researcher``

Does not dual product NEXT. Local solutions only (probes, docs-in-place,
plane economy). Escalates human-gated money blocks via Unblock checklist.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from veritas.block_board import Block, BlockBoard, seed_known_blocks


def _try_local_solve(block: Block) -> tuple[str, str, str | None]:
    """Return (status, resolution, report_extra). status: resolved|escalated|wontfix."""
    kind = block.kind
    title = block.title.lower()

    if kind == "money_egress" or "rpc" in title or "0.1" in title:
        # Run unblock probe in place — real local action
        try:
            from veritas.unblock_probe import run_probes, write_checklist

            probes = run_probes()
            path = write_checklist(probes)
            ready = all(
                probes.get(k, {}).get("status") == "yes"
                for k in ("VERITAS_RPC_URL", "facilitator")
            )
            if ready:
                return (
                    "resolved",
                    f"Unblock probe: RPC+facilitator ready. Checklist {path}. "
                    "Human funding still required before product 0.1 claim.",
                    str(path),
                )
            return (
                "escalated",
                f"Unblock probe ran; required rows not ready. Checklist {path}. "
                f"Probes: {json.dumps({k: v.get('status') for k, v in probes.items()})}. "
                "Blocked party: wait human RPC/wallet or keep HOLD.",
                str(path),
            )
        except Exception as e:  # noqa: BLE001
            return ("escalated", f"unblock_probe failed: {type(e).__name__}: {e}", None)

    if kind == "idle" or "idle-true" in title or "hold" in title:
        return (
            "resolved",
            "Confirmed WORKFLOW_HYGIENE idle-true. Blocked party should noop "
            "(no restock PR). Researcher will not invent product NEXT.",
            None,
        )

    if kind == "strategy":
        return (
            "escalated",
            "Strategy HOLD is Overseer-owned. Researcher will not invent NEXT. "
            "When Unblock flips ready, Overseer may name 0.1/G9.",
            None,
        )

    # Generic: leave claimed with research notes for human/LLM deep tick
    return (
        "escalated",
        "No automatic local solver for this kind. Deep research tick should "
        "expand detail and post code PR only under single claim if product.",
        None,
    )


def run_tick(
    *,
    base_dir: Path | str | None = None,
    researcher_id: str = "researcher",
    max_claims: int = 2,
    seed: bool = True,
) -> dict[str, Any]:
    base = Path(base_dir) if base_dir else Path.cwd() / ".veritas"
    base.mkdir(parents=True, exist_ok=True)
    board = BlockBoard(base / "block_board.sqlite3")
    if seed:
        seed_known_blocks(board)

    results: list[dict[str, Any]] = []
    open_blocks = board.list_open(limit=max_claims * 3)
    claimed = 0
    for block in open_blocks:
        if claimed >= max_claims:
            break
        try:
            block = board.claim(block.block_id, researcher_id)
        except Exception as e:  # noqa: BLE001
            results.append(
                {
                    "block_id": block.block_id,
                    "error": str(e),
                    "status": "claim_failed",
                }
            )
            continue
        claimed += 1
        status, resolution, extra = _try_local_solve(block)
        resolved = board.resolve(
            block.block_id,
            resolution,
            report_path=extra,
            status=status,
        )
        inbox = board.write_inbox(
            resolved.blocked_agent,
            resolved,
            reports_dir=Path.cwd()
            / "docs"
            / "program"
            / "researcher"
            / "inbox",
        )
        # Point report_path at inbox when not already set
        if not resolved.report_path:
            board.resolve(
                resolved.block_id,
                resolution,
                report_path=str(inbox),
                status=status,
            )
            resolved = board.get(resolved.block_id)
        results.append(
            {
                **resolved.to_dict(),
                "inbox": str(inbox),
                "extra": extra,
            }
        )

    snap = board.snapshot()
    board.close()
    return {
        "researcher_id": researcher_id,
        "ts": time.time(),
        "acted": results,
        "board": snap,
        "not_x402_settlement": True,
    }


def main() -> None:
    out = run_tick()
    print(json.dumps(out, indent=2, default=str))


if __name__ == "__main__":
    main()
