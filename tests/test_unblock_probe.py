"""L1: unblock probe checks pinned public defaults when env is unset.

The probe's job is to discover capability, so an unset env var must degrade
to probing the pinned public default (source labelled), never to "no" without
a probe. Network is faked at urlopen, so the suite never depends on external
uptime.
"""

from __future__ import annotations

import io
import json
import urllib.request

from veritas.unblock_probe import (
    DEFAULT_FACILITATOR,
    DEFAULT_TESTNET_RPC,
    run_probes,
    write_checklist,
)


class _FakeResponse(io.BytesIO):
    status = 200

    def getcode(self):  # pragma: no cover - status attribute is preferred
        return self.status

    def __exit__(self, *exc):
        self.close()
        return False

    def __enter__(self):
        return self


def _fake_urlopen(request, timeout=None):
    url = request.full_url if hasattr(request, "full_url") else str(request)
    # Cloudflare fronts both default endpoints and 403s an absent/default
    # Python-urllib agent (observed live 2026-08-09) — the probe must
    # identify itself or the defaults are unreachable in production.
    agent = request.get_header("User-agent", "")
    assert agent.startswith("veritas-unblock-probe/"), agent
    if url.startswith(DEFAULT_TESTNET_RPC):
        return _FakeResponse(
            json.dumps({"jsonrpc": "2.0", "id": 1, "result": "0x14a34"}).encode()
        )
    if url.startswith(DEFAULT_FACILITATOR):
        return _FakeResponse(b"{}")
    raise AssertionError(f"unexpected probe URL: {url}")


def test_unset_env_probes_pinned_defaults_with_labelled_source(monkeypatch):
    for var in (
        "VERITAS_RPC_URL",
        "VERITAS_FACILITATOR",
        "VERITAS_FACILITATOR_URL",
        "X402_FACILITATOR_URL",
        "BUYER_PRIVATE_KEY",
        "VERITAS_PRIVATE_KEY",
        "VERITAS_BUYER_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)

    probes = run_probes()

    rpc = probes["VERITAS_RPC_URL"]
    assert rpc["status"] == "yes"
    assert "0x14a34" in rpc["evidence"]
    assert DEFAULT_TESTNET_RPC in rpc["evidence"]
    assert "unset" in rpc["evidence"], "must say the env override is absent"

    fac = probes["facilitator"]
    assert fac["status"] == "yes"
    assert DEFAULT_FACILITATOR in fac["evidence"]


def test_env_url_overrides_the_default(monkeypatch):
    monkeypatch.setenv("VERITAS_RPC_URL", "https://operator.example/rpc")
    monkeypatch.delenv("VERITAS_FACILITATOR_URL", raising=False)
    monkeypatch.delenv("X402_FACILITATOR_URL", raising=False)
    seen = []

    def fake(request, timeout=None):
        url = request.full_url if hasattr(request, "full_url") else str(request)
        seen.append(url)
        if "operator.example" in url:
            return _FakeResponse(
                json.dumps({"jsonrpc": "2.0", "id": 1, "result": "0x1"}).encode()
            )
        return _FakeResponse(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    probes = run_probes()
    assert any("operator.example" in u for u in seen)
    assert DEFAULT_TESTNET_RPC not in " ".join(seen)
    assert "pinned public default" not in probes["VERITAS_RPC_URL"]["evidence"]


def test_write_checklist_no_secrets_and_no_stale_settle_claim(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(urllib.request, "urlopen", _fake_urlopen)
    for var in (
        "VERITAS_RPC_URL",
        "VERITAS_FACILITATOR",
        "VERITAS_FACILITATOR_URL",
        "X402_FACILITATOR_URL",
        "BUYER_PRIVATE_KEY",
        "VERITAS_PRIVATE_KEY",
        "VERITAS_BUYER_KEY",
    ):
        monkeypatch.delenv(var, raising=False)
    probes = run_probes()
    path = write_checklist(probes, path=tmp_path / "CHECKLIST.md")
    text = path.read_text(encoding="utf-8")
    assert "VERITAS_RPC_URL" in text
    # The checklist points at settlement evidence instead of restating a
    # count that goes stale (MIND §5).
    assert "remains **0**" not in text
    assert "fable/settlement" in text
    # Wallet key rows never echo key material.
    assert "0x" not in text.split("| wallet_key_configured")[-1].split("|")[2]
