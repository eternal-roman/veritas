"""Existence landmass must not invent demand.

The scorecard still ships (`veritas-ops existence`, agent readiness).
These tests pin the only product-honesty property it has: confirmed
settlement counts come from transcripts, and unsolicited/mainnet stay 0
unless evidence says otherwise. File-tree "surfaces exist" checks and
injected PyPI/host probes do not make a payment or a retrieval more correct.
"""

from __future__ import annotations

import json
from pathlib import Path

from veritas.existence import SCHEMA, build_existence_report, scan_settlement_evidence


def _write_settlement(path: Path, *, met: bool, tx: str | None) -> None:
    body = {
        "acceptance": {"met": met, "transaction": tx},
        "proof": {
            "settlement": {
                "settled": met,
                "transaction": tx,
            }
        },
    }
    path.write_text(json.dumps(body), encoding="utf-8")


def _write_money_loop(path: Path, *, met: bool, tx: str | None) -> None:
    body = {
        "phase": "0.1-R",
        "acceptance": {"met": met, "notes": []},
        "settle": {"acceptance": {"met": met, "transaction": tx}},
        "reconcile": {"chain_checked": met, "counts": {"confirmed": 1 if met else 0}},
    }
    path.write_text(json.dumps(body), encoding="utf-8")


def test_scan_counts_only_met_with_real_tx(tmp_path: Path) -> None:
    good = "0x" + "ab" * 32
    _write_settlement(tmp_path / "settlement_ok.json", met=True, tx=good)
    _write_settlement(tmp_path / "settlement_fail.json", met=False, tx=None)
    _write_settlement(
        tmp_path / "settlement_fake_tx.json",
        met=True,
        tx="0xnotarealtx",
    )
    _write_settlement(tmp_path / "settlement_dup.json", met=True, tx=good)

    report = scan_settlement_evidence(tmp_path)
    assert report["files_scanned"] == 4
    assert report["testnet_settlements_confirmed"] == 1
    assert report["transactions"] == [good.lower()]
    assert report["incomplete_or_failed_runs"] == 2


def test_scan_counts_money_loop_transcripts(tmp_path: Path) -> None:
    """Both transcript families count; a tx that appears in both is one."""
    tx_a = "0x" + "11" * 32
    tx_b = "0x" + "22" * 32
    _write_settlement(tmp_path / "settlement_one.json", met=True, tx=tx_a)
    _write_money_loop(tmp_path / "money_loop_two.json", met=True, tx=tx_b)
    _write_money_loop(tmp_path / "money_loop_honest_exit2.json", met=False, tx=None)
    _write_money_loop(tmp_path / "money_loop_dup.json", met=True, tx=tx_a)

    report = scan_settlement_evidence(tmp_path)
    assert report["files_scanned"] == 4
    assert report["testnet_settlements_confirmed"] == 2
    assert sorted(report["transactions"]) == sorted([tx_a.lower(), tx_b.lower()])
    assert report["incomplete_or_failed_runs"] == 1


def test_build_report_never_invents_unsolicited_or_mainnet(tmp_path: Path) -> None:
    good = "0x" + "cd" * 32
    _write_settlement(tmp_path / "settlement_a.json", met=True, tx=good)
    report = build_existence_report(evidence_dir=tmp_path, repo_root=tmp_path)
    assert report["schema"] == SCHEMA
    assert report["landmass"]["testnet_settlements_confirmed"] == 1
    assert report["landmass"]["unsolicited_settlements"] == 0
    assert report["landmass"]["mainnet_settlements"] == 0
    assert report["stage1"]["pypi_published"] is False
    assert "unsolicited demand" in report["not_proven"]
