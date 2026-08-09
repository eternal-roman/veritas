"""Stage-1 existence scorecard — landmass from evidence, never invented demand."""

from __future__ import annotations

import json
from pathlib import Path

from veritas.existence import (
    SCHEMA,
    build_existence_report,
    probe_public_host,
    probe_pypi,
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


def _write_money_loop(path: Path, *, met: bool, tx: str | None) -> None:
    # The composed 0.1-R transcript shape: top-level acceptance, tx nested
    # under settle.acceptance (veritas.money_loop.run_money_loop evidence).
    body = {
        "phase": "0.1-R",
        "acceptance": {"met": met, "notes": []},
        "settle": {"acceptance": {"met": met, "transaction": tx}},
        "reconcile": {"chain_checked": met, "counts": {"confirmed": 1 if met else 0}},
    }
    path.write_text(json.dumps(body), encoding="utf-8")


def test_scan_counts_money_loop_transcripts(tmp_path: Path) -> None:
    """The first live money-loop run was invisible to the scorecard: only
    settlement_*.json was globbed, so the measured signal undercounted the
    evidence on disk. Both transcript families must count, without double-
    counting a tx that appears in both."""
    tx_a = "0x" + "11" * 32
    tx_b = "0x" + "22" * 32
    _write_settlement(tmp_path / "settlement_one.json", met=True, tx=tx_a)
    _write_money_loop(tmp_path / "money_loop_two.json", met=True, tx=tx_b)
    _write_money_loop(tmp_path / "money_loop_honest_exit2.json", met=False, tx=None)
    # Same tx re-logged by both families must not inflate the unique count.
    _write_money_loop(tmp_path / "money_loop_dup.json", met=True, tx=tx_a)

    report = scan_settlement_evidence(tmp_path)
    assert report["files_scanned"] == 4
    assert report["testnet_settlements_confirmed"] == 2
    assert sorted(report["transactions"]) == sorted([tx_a.lower(), tx_b.lower()])
    assert report["incomplete_or_failed_runs"] == 1


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
    (root / "veritas" / "existence.py").write_text("#", encoding="utf-8")
    (root / "veritas" / "buyer_journey.py").write_text("#", encoding="utf-8")

    report = build_existence_report(evidence_dir=tmp_path, repo_root=root)
    assert report["schema"] == SCHEMA
    assert report["landmass"]["testnet_settlements_confirmed"] == 1
    assert report["landmass"]["unsolicited_settlements"] == 0
    assert report["landmass"]["mainnet_settlements"] == 0
    assert report["stage1"]["pypi_published"] is False
    assert "pypi_trusted_publisher" in report["stage1"]["human_minutes_remaining"]
    assert report["agent_ready_surfaces"]["notary_package"] is True
    assert report["agent_ready_surfaces"]["dogfood_commerce"] is True
    assert report["publicly_existable"] is False
    assert report["probe_ran"] is False
    assert report["stage1_prep"]["vision_stage"] == "1_public_existence"
    assert report["stage1_prep"]["agent_prep_complete"] is True
    assert "unsolicited demand" in report["not_proven"]


def test_probe_pypi_404_is_not_published() -> None:
    def fake_get(url: str) -> tuple[int, bytes]:
        assert "pypi.org" in url
        return 404, b"Not Found"

    out = probe_pypi(http_get=fake_get)
    assert out["published"] is False
    assert out["http_status"] == 404
    assert out["probed"] is True


def test_probe_pypi_200_is_published() -> None:
    body = json.dumps({"info": {"version": "0.9.0"}}).encode("utf-8")

    def fake_get(url: str) -> tuple[int, bytes]:
        return 200, body

    out = probe_pypi(http_get=fake_get)
    assert out["published"] is True
    assert out["pypi_version"] == "0.9.0"


def test_probe_public_host_health_ok() -> None:
    def fake_get(url: str) -> tuple[int, bytes]:
        assert url.endswith("/health")
        return 200, json.dumps({"mode": "free"}).encode("utf-8")

    out = probe_public_host("https://seller.example", http_get=fake_get)
    assert out["ok"] is True
    assert out["https"] is True
    assert out["health_mode"] == "free"


def test_build_report_with_probe_injection(tmp_path: Path, monkeypatch) -> None:
    good = "0x" + "ab" * 32
    _write_settlement(tmp_path / "settlement_a.json", met=True, tx=good)
    root = tmp_path / "repo"
    (root / "veritas" / "notary").mkdir(parents=True)
    for rel in (
        "veritas/notary/observe.py",
        "veritas/verifier.py",
        "veritas/money_loop.py",
        "veritas/buyer_journey.py",
        "veritas/existence.py",
        "veritas/chain_reconcile.py",
        "veritas/evaluations/product_worth.py",
        "scripts/dogfood_agent_commerce.py",
        "scripts/circle_faucet_playwright.py",
        ".github/workflows/release.yml",
    ):
        path = root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("#", encoding="utf-8")

    monkeypatch.setenv("VERITAS_PUBLIC_URL", "https://seller.example")

    def fake_get(url: str) -> tuple[int, bytes]:
        if "pypi.org" in url:
            return 404, b"Not Found"
        if url.endswith("/health"):
            return 200, b'{"mode":"live"}'
        return 500, b""

    report = build_existence_report(
        evidence_dir=tmp_path,
        repo_root=root,
        probe=True,
        http_get=fake_get,
    )
    assert report["probe_ran"] is True
    assert report["probes"]["pypi"]["published"] is False
    assert report["probes"]["public_host"]["ok"] is True
    assert report["publicly_existable"] is False  # PyPI still human
    assert "not_on_pypi" in report["stage1_prep"]["human_status"][
        "pypi_trusted_publisher"
    ]


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
