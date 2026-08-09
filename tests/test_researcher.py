"""L1: researcher tick claims blocks and reports back."""

from __future__ import annotations

from veritas.researcher import run_tick


def test_researcher_tick_local(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # inbox writes under cwd/docs/program/researcher/inbox
    out = run_tick(base_dir=tmp_path / ".veritas", max_claims=2, seed=True)
    assert out["not_x402_settlement"] is True
    assert len(out["acted"]) >= 1
    # money egress should escalate or resolve after probe
    kinds = {a.get("kind") for a in out["acted"]}
    assert kinds
    inbox = tmp_path / "docs" / "program" / "researcher" / "inbox"
    assert inbox.is_dir()
    assert any(inbox.iterdir())
