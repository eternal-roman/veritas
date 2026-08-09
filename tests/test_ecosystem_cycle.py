"""L1: ecosystem mesh cycle kernel advances tracks."""

from __future__ import annotations

from pathlib import Path

from veritas.ecosystem_cycle import run_cycles


def test_run_five_cycles(tmp_path: Path):
    # Minimal program tree
    eco = tmp_path / "docs" / "program" / "ecosystem"
    for tid in (
        "money_loop",
        "multiparty_trust",
        "product_worth",
        "discovery_density",
        "multi_tenant",
        "legal_identity",
        "network_effects",
    ):
        d = eco / tid
        d.mkdir(parents=True)
        (d / "CURRENT.md").write_text(
            f"# x\n\n- **Track:** `{tid}`\n- **Status:** open\n- **Cycle:** 0\n",
            encoding="utf-8",
        )

    out = run_cycles(tmp_path, cycles=5, base_dir=tmp_path / ".veritas")
    assert out["cycles_run"] == 5
    assert out["not_x402_settlement"] is True
    assert out["tracks"]["money_loop"]["cycle"] == 5
    assert out["tracks"]["discovery_density"]["cycle"] == 5
    bus = (eco / "BUS.md").read_text(encoding="utf-8")
    assert "money_loop" in bus
    learn = list((eco / "learn").glob("*.md"))
    assert learn
    # money_loop should rank at or near top in last report
    ranking = out["reports"][-1]["ranking"]
    assert ranking[0] in ("money_loop", "product_worth", "multiparty_trust")
