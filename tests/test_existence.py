"""Stage-1 existence scorecard — landmass from evidence, never invented demand."""

from __future__ import annotations

import json
from pathlib import Path

from veritas.existence import (
    SCHEMA,
    build_existence_report,
    scan_settlement_evidence,
)
from veritas.existence import (
    main as existence_main,
)
from veritas.ops_cli import main as ops_main


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


def test_scan_counts_only_met_with_real_tx(tmp_path: Path) -> None:
    good = "0x" + "ab" * 32
    _write_settlement(tmp_path / "settlement_ok.json", met=True, tx=good)
    _write_settlement(tmp_path / "settlement_fail.json", met=False, tx=None)
    _write_settlement(
        tmp_path / "settlement_fake_tx.json",
        met=True,
        tx="0xnotarealtx",
    )
    # duplicate same tx in second confirmed file should not inflate unique count
    _write_settlement(tmp_path / "settlement_dup.json", met=True, tx=good)

    report = scan_settlement_evidence(tmp_path)
    assert report["files_scanned"] == 4
    assert report["testnet_settlements_confirmed"] == 1
    assert report["transactions"] == [good.lower()]
    assert report["incomplete_or_failed_runs"] == 2


def test_build_report_never_invents_unsolicited_or_mainnet(tmp_path: Path) -> None:
    good = "0x" + "cd" * 32
    _write_settlement(tmp_path / "settlement_a.json", met=True, tx=good)
    # Minimal fake repo root with a couple of surfaces
    root = tmp_path / "repo"
    (root / "veritas" / "notary").mkdir(parents=True)
    (root / "veritas" / "notary" / "observe.py").write_text("#", encoding="utf-8")
    (root / "veritas" / "verifier.py").write_text("#", encoding="utf-8")
    (root / "veritas" / "money_loop.py").write_text("#", encoding="utf-8")
    (root / "veritas" / "evaluations").mkdir(parents=True)
    (root / "veritas" / "evaluations" / "product_worth.py").write_text(
        "#", encoding="utf-8"
    )
    (root / "scripts").mkdir()
    (root / "scripts" / "dogfood_agent_commerce.py").write_text("#", encoding="utf-8")
    (root / "scripts" / "circle_faucet_playwright.py").write_text("#", encoding="utf-8")
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "release.yml").write_text("#", encoding="utf-8")
    (root / "veritas" / "chain_reconcile.py").write_text("#", encoding="utf-8")

    report = build_existence_report(evidence_dir=tmp_path, repo_root=root)
    assert report["schema"] == SCHEMA
    assert report["landmass"]["testnet_settlements_confirmed"] == 1
    assert report["landmass"]["unsolicited_settlements"] == 0
    assert report["landmass"]["mainnet_settlements"] == 0
    assert report["stage1"]["pypi_published"] is False
    assert "pypi_trusted_publisher" in report["stage1"]["human_minutes_remaining"]
    assert report["agent_ready_surfaces"]["notary_package"] is True
    assert report["agent_ready_surfaces"]["dogfood_commerce"] is True
    assert "unsolicited demand" in report["not_proven"]


def test_cli_module_and_ops_existence(tmp_path: Path, capsys) -> None:
    good = "0x" + "ef" * 32
    _write_settlement(tmp_path / "settlement_z.json", met=True, tx=good)

    code = existence_main(["--evidence-dir", str(tmp_path)])
    assert code == 0
    out = json.loads(capsys.readouterr().out)
    assert out["landmass"]["testnet_settlements_confirmed"] == 1

    code = ops_main(
        ["--runtime-dir", str(tmp_path / "runtime"), "existence",
         "--evidence-dir", str(tmp_path)]
    )
    assert code == 0
    out2 = json.loads(capsys.readouterr().out)
    assert out2["schema"] == SCHEMA
    assert out2["landmass"]["transactions"] == [good.lower()]
