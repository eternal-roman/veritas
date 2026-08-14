"""veritas-diligence: the verdict must survive into the process contract.

An agent shelling out to this tool sees only stdout and an exit code, so the
UNVERIFIABLE/FAIL distinction has to be visible in both or it is not really
being made.
"""

from __future__ import annotations

import json

from veritas import diligence_cli
from veritas.diligence_cli import (
    EXIT_BAD_INPUT,
    EXIT_FAIL,
    EXIT_PASS,
    EXIT_UNVERIFIABLE,
    main,
)

BASE = "https://seller.test"
PAY_TO = "0x" + "11" * 20
ASSET = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"


def _accepts(pay_to=PAY_TO):
    return {
        "scheme": "exact", "network": "eip155:8453", "asset": ASSET,
        "payTo": pay_to, "maxAmountRequired": "10000",
        "resource": f"{BASE}/v1/research",
        "extra": {"name": "USD Coin", "version": "2"},
    }


DISCOVERY = {"x402Version": 1, "accepts": [_accepts()],
             "links": {"constitution": "/v1/constitution", "trust": "/v1/trust"}}
CONSTITUTION = {
    "articles": [{"id": "A1", "evidence_level": "L1",
                  "enforcement": [{"kind": "test", "pointer": "tests/t.py::x"}]}],
    "known_gaps": [{"id": "G10", "status": "open"}],
}
TRUST = {"recommendation": "UNPROVEN",
         "basis": {"min_samples": 10, "score_source": "independent_audits"}}


def _install(monkeypatch, pages):
    """Point the CLI at a fake seller instead of the network."""
    real = diligence_cli.evaluate_seller

    def fake(url, **kw):
        kw.setdefault("resolver", lambda h, p=None, *a, **k: [
            (2, 1, 6, "", ("93.184.216.34", 0))])
        kw["fetch"] = lambda u: (
            json.dumps(pages[u]).encode() if u in pages
            else (_ for _ in ()).throw(OSError(f"404 {u}"))
        )
        return real(url, **kw)

    monkeypatch.setattr(diligence_cli, "evaluate_seller", fake)


def _healthy():
    return {f"{BASE}/.well-known/x402": DISCOVERY,
            f"{BASE}/v1/constitution": CONSTITUTION,
            f"{BASE}/v1/trust": TRUST}


def test_a_clean_seller_exits_zero(monkeypatch, capsys):
    _install(monkeypatch, _healthy())
    assert main([BASE]) == EXIT_PASS
    body = json.loads(capsys.readouterr().out)
    assert body["verdict"] == "pass"
    assert body["seller"] == BASE


def test_a_contradictory_seller_exits_one(monkeypatch, capsys, tmp_path):
    _install(monkeypatch, _healthy())
    challenge = tmp_path / "challenge.json"
    challenge.write_text(json.dumps({"accepts": [_accepts(pay_to="0x" + "22" * 20)]}),
                         encoding="utf-8")

    assert main([BASE, "--challenge", str(challenge)]) == EXIT_FAIL
    body = json.loads(capsys.readouterr().out)
    assert body["verdict"] == "fail"
    assert any("pay_to" in r for r in body["reasons"])


def test_an_unreachable_seller_exits_two_not_one(monkeypatch, capsys):
    """The whole point of a separate exit code: an agent must not treat its own
    network trouble as the seller's misconduct."""
    _install(monkeypatch, {})
    assert main([BASE]) == EXIT_UNVERIFIABLE
    assert json.loads(capsys.readouterr().out)["verdict"] == "unverifiable"


def test_an_unsafe_url_is_the_buyers_error_not_a_verdict(capsys):
    assert main(["file:///etc/passwd"]) == EXIT_BAD_INPUT
    body = json.loads(capsys.readouterr().out)
    assert body["error"] == "unsafe_url"
    assert "verdict" not in body


def test_an_unreadable_challenge_file_is_the_buyers_error(capsys, tmp_path):
    bad = tmp_path / "nope.json"
    bad.write_text("{not json", encoding="utf-8")
    assert main([BASE, "--challenge", str(bad)]) == EXIT_BAD_INPUT
    assert json.loads(capsys.readouterr().out)["error"] == "challenge_unreadable"


def test_gap_requirement_can_be_waived(monkeypatch, capsys):
    pages = _healthy()
    pages[f"{BASE}/v1/constitution"] = {**CONSTITUTION, "known_gaps": []}
    _install(monkeypatch, pages)

    assert main([BASE]) == EXIT_FAIL
    capsys.readouterr()
    assert main([BASE, "--allow-undeclared-gaps"]) == EXIT_PASS


def test_output_is_machine_readable_with_a_reason_per_check(monkeypatch, capsys):
    _install(monkeypatch, _healthy())
    main([BASE])
    body = json.loads(capsys.readouterr().out)
    assert isinstance(body["checks"], list) and body["checks"]
    for check in body["checks"]:
        assert set(check) == {"name", "verdict", "detail"}
