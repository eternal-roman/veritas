"""Stage-1 existence scorecard — measured landmass, never invented demand.

Answers what the vision path (REFOUNDING Stage 1) needs operators and agents
to track without restating stale card facts:

* how many **self-dogfood** testnet settlements have evidence on disk
* that **unsolicited** and **mainnet** remain zero until measured elsewhere
* which Stage-1 human residues remain (PyPI / TLS / mainnet pay-to)
* which agent-ready surfaces already ship (notary, dogfood, money_loop, …)

This module does **not** claim unsolicited demand, mainnet success, or
commercial product-worth. Run::

    python -m veritas.existence
    veritas-ops existence
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from veritas import __version__

SCHEMA = "veritas.existence.v0"

# Repo-relative default: durable settlement transcripts from live contact.
DEFAULT_SETTLEMENT_DIR = Path("docs") / "program" / "fable" / "settlement"

# Human Stage-1 residues (REFOUNDING §4). Agents prepare 90%; humans finish.
STAGE1_HUMAN = (
    "pypi_trusted_publisher",
    "public_tls_host",
    "mainnet_pay_to",
    "registry_listing",
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _is_tx_hash(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not (s.startswith("0x") or s.startswith("0X")):
        return False
    body = s[2:]
    return len(body) == 64 and all(c in "0123456789abcdefABCDEF" for c in body)


def _walk_tx_hashes(obj: Any, out: list[str]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in ("transaction", "tx_hash", "transactionHash") and _is_tx_hash(v):
                out.append(v.lower())
            else:
                _walk_tx_hashes(v, out)
    elif isinstance(obj, list):
        for item in obj:
            _walk_tx_hashes(item, out)


def scan_settlement_evidence(evidence_dir: Path) -> dict[str, Any]:
    """Count confirmed self-dogfood settlements from on-disk JSON transcripts.

    A file counts when ``acceptance.met`` is true **and** a 32-byte 0x
    transaction hash appears (acceptance.transaction or nested proof).
    Both transcript families count: ``settlement_*.json`` (direct recipe) and
    ``money_loop_*.json`` (composed 0.1-R runs) — the first live money-loop
    run was invisible to this scorecard because only the former was globbed,
    which made the measured signal undercount the evidence on disk.
    """
    confirmed: list[dict[str, Any]] = []
    incomplete = 0
    unreadable = 0

    if not evidence_dir.is_dir():
        return {
            "evidence_dir": str(evidence_dir),
            "files_scanned": 0,
            "testnet_settlements_confirmed": 0,
            "incomplete_or_failed_runs": 0,
            "unreadable": 0,
            "transactions": [],
            "by_file": [],
        }

    files = sorted(
        set(evidence_dir.glob("settlement_*.json"))
        | set(evidence_dir.glob("money_loop_*.json"))
    )
    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            unreadable += 1
            continue

        acc = data.get("acceptance") if isinstance(data, dict) else None
        met = bool(isinstance(acc, dict) and acc.get("met") is True)
        txs: list[str] = []
        if isinstance(acc, dict) and _is_tx_hash(acc.get("transaction")):
            txs.append(str(acc["transaction"]).lower())
        _walk_tx_hashes(data, txs)
        # de-dupe preserve order
        seen: set[str] = set()
        uniq: list[str] = []
        for t in txs:
            if t not in seen:
                seen.add(t)
                uniq.append(t)

        if met and uniq:
            confirmed.append(
                {
                    "file": path.name,
                    "transaction": uniq[0],
                    "all_transactions": uniq,
                }
            )
        else:
            incomplete += 1

    # Unique txs across files (same settle re-logged should not inflate n).
    all_tx: list[str] = []
    seen_tx: set[str] = set()
    for row in confirmed:
        t = row["transaction"]
        if t not in seen_tx:
            seen_tx.add(t)
            all_tx.append(t)

    return {
        "evidence_dir": str(evidence_dir),
        "files_scanned": len(files),
        "testnet_settlements_confirmed": len(all_tx),
        "incomplete_or_failed_runs": incomplete,
        "unreadable": unreadable,
        "transactions": all_tx,
        "by_file": confirmed,
    }


def _agent_surfaces(root: Path) -> dict[str, bool]:
    return {
        "notary_package": (root / "veritas" / "notary" / "observe.py").is_file(),
        "verifier_entrypoint": (root / "veritas" / "verifier.py").is_file(),
        "money_loop": (root / "veritas" / "money_loop.py").is_file(),
        "product_worth": (
            root / "veritas" / "evaluations" / "product_worth.py"
        ).is_file(),
        "buyer_journey": (root / "veritas" / "buyer_journey.py").is_file(),
        "dogfood_commerce": (
            root / "scripts" / "dogfood_agent_commerce.py"
        ).is_file(),
        "circle_faucet_playwright": (
            root / "scripts" / "circle_faucet_playwright.py"
        ).is_file(),
        "release_workflow": (root / ".github" / "workflows" / "release.yml").is_file(),
        "chain_reconcile": (root / "veritas" / "chain_reconcile.py").is_file(),
    }


def _stage1_residues() -> dict[str, Any]:
    """Env-visible residues only — never invent PyPI/TLS success."""
    public_url = (os.environ.get("VERITAS_PUBLIC_URL") or "").strip()
    pay_to = (os.environ.get("VERITAS_PAY_TO") or "").strip()
    network = (os.environ.get("VERITAS_NETWORK") or "").strip().lower()
    mainnetish = network in ("base", "eip155:8453", "8453")

    remaining = list(STAGE1_HUMAN)
    # Agents cannot clear these; we only note when env already points live.
    notes: list[str] = []
    if public_url.startswith("https://"):
        notes.append("VERITAS_PUBLIC_URL is https (TLS host may still need DNS)")
    if pay_to.startswith("0x") and mainnetish:
        notes.append("mainnet-ish pay-to env present — human still owns funding risk")

    return {
        "human_minutes_remaining": remaining,
        "env_hints": {
            "VERITAS_PUBLIC_URL_set": bool(public_url),
            "VERITAS_PUBLIC_URL_https": public_url.startswith("https://"),
            "VERITAS_PAY_TO_set": bool(pay_to),
            "VERITAS_NETWORK": network or None,
            "looks_mainnet_network": mainnetish,
        },
        "notes": notes,
        "pypi_published": False,  # never invent; human/registry probe is separate
        "unsolicited_settlements": 0,
        "mainnet_settlements": 0,
    }


def build_existence_report(
    *,
    evidence_dir: Path | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    root = repo_root or _repo_root()
    settlements = evidence_dir or (root / DEFAULT_SETTLEMENT_DIR)
    landmass = scan_settlement_evidence(settlements)
    surfaces = _agent_surfaces(root)
    stage1 = _stage1_residues()

    return {
        "schema": SCHEMA,
        "package_version": __version__,
        "landmass": {
            "testnet_settlements_confirmed": landmass[
                "testnet_settlements_confirmed"
            ],
            "mainnet_settlements": stage1["mainnet_settlements"],
            "unsolicited_settlements": stage1["unsolicited_settlements"],
            "transactions": landmass["transactions"],
            "evidence": {
                "dir": landmass["evidence_dir"],
                "files_scanned": landmass["files_scanned"],
                "incomplete_or_failed_runs": landmass["incomplete_or_failed_runs"],
                "unreadable": landmass["unreadable"],
                "by_file": landmass["by_file"],
            },
            "source": "on_disk_settlement_transcripts",
            "not_from_ledger_alone": True,
        },
        "stage1": stage1,
        "agent_ready_surfaces": surfaces,
        "vision_path": {
            "stage0_rails": "done (live facilitator settle proven in evidence)",
            "stage1_public_existence": "open — human residues + unsolicited=0",
            "stage2_substrate_product": "parked until stage1 falsifier window runs",
            "falsifier_stage1": (
                "90 days listed with zero unsolicited paid requests from any "
                "counterparty we did not build"
            ),
        },
        "not_proven": [
            "unsolicited demand",
            "mainnet settlement",
            "PyPI publish",
            "public TLS production host",
            "commercial product-worth",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="veritas-existence",
        description=(
            "Stage-1 existence scorecard from on-disk settlement evidence. "
            "JSON on stdout. Never invents unsolicited or mainnet success."
        ),
    )
    parser.add_argument(
        "--evidence-dir",
        type=Path,
        default=None,
        help=f"Settlement transcript directory (default: {DEFAULT_SETTLEMENT_DIR})",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=None,
        help="Repository root for surface checks (default: package parent).",
    )
    args = parser.parse_args(argv)
    report = build_existence_report(
        evidence_dir=args.evidence_dir,
        repo_root=args.repo_root,
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
