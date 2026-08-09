"""L1: unblock probe writes checklist without secrets."""

from __future__ import annotations

from veritas.unblock_probe import run_probes, write_checklist


def test_write_checklist(tmp_path, monkeypatch):
    monkeypatch.delenv("VERITAS_RPC_URL", raising=False)
    monkeypatch.delenv("VERITAS_FACILITATOR_URL", raising=False)
    monkeypatch.delenv("X402_FACILITATOR_URL", raising=False)
    monkeypatch.delenv("VERITAS_PRIVATE_KEY", raising=False)
    monkeypatch.delenv("VERITAS_BUYER_KEY", raising=False)
    probes = run_probes()
    assert probes["VERITAS_RPC_URL"]["status"] == "no"
    path = write_checklist(probes, path=tmp_path / "CHECKLIST.md")
    text = path.read_text(encoding="utf-8")
    assert "VERITAS_RPC_URL" in text
    assert "not_x402" not in text.lower() or "settle" in text.lower()
    assert "unknown" in text or "no" in text
