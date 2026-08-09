"""L1: plane_stock snapshot shape + continuous-org v5 stall signals."""

from __future__ import annotations

from veritas.plane_stock import _claim, _stall_signals, stock


def test_stock_shape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    claim = tmp_path / "docs" / "program" / "flywheel-claim.md"
    claim.parent.mkdir(parents=True)
    claim.write_text("**status:** free\n", encoding="utf-8")
    s = stock(tmp_path)
    assert s["claim"]["status"] == "free"
    assert "open_prs" in s
    assert "stall" in s
    assert s["stall"]["claim_stale_building"] is False
    assert s["not_x402_settlement"] is True
    assert s["stock_protocol"] == "plane_stock_v2"


def test_claim_parses_building_fields(tmp_path):
    claim = tmp_path / "flywheel-claim.md"
    claim.write_text(
        "\n".join(
            [
                "# flywheel-claim",
                "",
                "- **bet_id:** phase-0.1-R",
                "- **branch:** feat/phase-0.1-R-routine-money-loop",
                "- **holder:** agent-commerce-flywheel",
                "- **status:** building",
                "- **updated:** 2026-08-09T03:05:00Z",
                "- **pr:** https://github.com/eternal-roman/veritas/pull/122",
                "",
            ]
        ),
        encoding="utf-8",
    )
    c = _claim(claim)
    assert c["status"] == "building"
    assert c["bet_id"] == "phase-0.1-R"
    assert c["branch"] == "feat/phase-0.1-R-routine-money-loop"
    assert c["pr"] and "122" in c["pr"]


def test_claim_none_and_pending_branch_are_empty(tmp_path):
    claim = tmp_path / "flywheel-claim.md"
    claim.write_text(
        "\n".join(
            [
                "- **bet_id:** (none)",
                "- **branch:** (pending — flywheel/implement)",
                "- **status:** free",
            ]
        ),
        encoding="utf-8",
    )
    c = _claim(claim)
    assert c["status"] == "free"
    assert c["bet_id"] is None
    assert c["branch"] is None


def test_stall_building_without_product_pr():
    claim = {
        "status": "building",
        "bet_id": "phase-0.1-R",
        "branch": None,
        "pr": None,
    }
    prs = {"ok": True, "product": [], "docs": [], "all": []}
    s = _stall_signals(claim, prs)
    assert s["building_without_product_pr"] is True
    assert s["building_without_branch"] is True
    assert s["claim_stale_building"] is True
    assert s["stall_action"] == "free_or_ship"
    assert s["stall_clock_active"] is True


def test_stall_building_with_product_pr_is_poll_not_stale():
    claim = {
        "status": "building",
        "bet_id": "x",
        "branch": "feat/x",
        "pr": "https://example/pr/1",
    }
    prs = {
        "ok": True,
        "product": [{"number": 1, "title": "feat x", "head": "feat/x"}],
        "docs": [],
        "all": [],
    }
    s = _stall_signals(claim, prs)
    assert s["building_without_product_pr"] is False
    assert s["claim_stale_building"] is False
    assert s["stall_action"] == "poll_ci_or_merge"


def test_stall_free_claim_no_stall():
    claim = {"status": "free", "bet_id": None, "branch": None, "pr": None}
    prs = {"ok": True, "product": [], "docs": [{"number": 2}], "all": []}
    s = _stall_signals(claim, prs)
    assert s["claim_stale_building"] is False
    assert s["hygiene_open"] is True
    assert s["stall_action"] is None
