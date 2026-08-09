"""L1: plane_stock snapshot shape (no network required for tip/claim)."""

from __future__ import annotations

from veritas.plane_stock import stock


def test_stock_shape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # minimal claim file
    claim = tmp_path / "docs" / "program" / "flywheel-claim.md"
    claim.parent.mkdir(parents=True)
    claim.write_text("**status:** free\n", encoding="utf-8")
    # fake git by letting stock fail soft on tip
    s = stock(tmp_path)
    assert s["claim"]["status"] == "free"
    assert "open_prs" in s
    assert s["not_x402_settlement"] is True
    assert s["stock_protocol"] == "plane_stock_v1"
