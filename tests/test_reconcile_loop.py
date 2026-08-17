"""Routine G9 compose + alert hook.

PROPERTY: one pass runs local reconcile and chain classify, does not
rewrite the ledger, and POSTs to a scheme-checked alert URL only when
the report is not clean. file: URLs are refused.

EVIDENCE LEVEL: L1 against a fake transport. NOT proven: a live mainnet
RPC, an operator webhook that pages a human.
"""

from __future__ import annotations

import json

from veritas.ledger import Ledger
from veritas.ops_cli import main
from veritas.reconcile_loop import run_loop, run_once, send_alert

NONCE = "0x" + "ab" * 32
OFFER = {
    "network": "eip155:84532",
    "asset": "0x036CbD53842c5426634e7929541eC2318f3dCF7e",
    "amount": "10000",
    "pay_to": "0x" + "11" * 20,
    "price": "$0.01",
}


def test_once_reports_local_and_chain_without_rewriting(tmp_path):
    ledger = Ledger(tmp_path)
    ledger.claim(NONCE, "req-1", **OFFER)
    ledger.record_delivery(
        "req-1", status="completed", billable=True,
        custody_root="sha256:r", query="q", response={},
    )
    before = ledger.authorization(NONCE).state
    report = run_once(ledger, transport=lambda url, method, params: None)
    after = ledger.authorization(NONCE).state
    assert before == after
    assert report["local"]["needs_attention"]
    assert "chain" in report
    assert report["needs_alert"] is True
    assert report["alerted"] is False


def test_file_alert_url_is_refused():
    result = send_alert("file:///etc/passwd", {"needs_alert": True})
    assert result["ok"] is False
    assert "refused" in result["error"]


def test_alert_posts_when_dirty(tmp_path, monkeypatch):
    posted: list[dict] = []

    def fake_urlopen(request, timeout=0):  # noqa: ARG001
        posted.append({
            "url": request.full_url,
            "body": json.loads(request.data.decode("utf-8")),
            "ua": request.headers.get("User-agent") or request.get_header("User-agent"),
        })

        class _Resp:
            status = 204

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

        return _Resp()

    monkeypatch.setattr("veritas.reconcile_loop.urllib.request.urlopen", fake_urlopen)
    ledger = Ledger(tmp_path)
    ledger.claim(NONCE, "req-1", **OFFER)
    ledger.record_delivery(
        "req-1", status="completed", billable=True,
        custody_root="sha256:r", query="q", response={},
    )
    report = run_once(
        ledger,
        alert_url="https://alerts.example/hook",
        transport=lambda url, method, params: None,
    )
    assert report["alerted"] is True
    assert posted and posted[0]["url"] == "https://alerts.example/hook"
    assert posted[0]["body"]["needs_alert"] is True
    assert "veritas-reconcile-loop/" in (posted[0]["ua"] or "")


def test_cli_once_prints_json(tmp_path, capsys):
    code = main(["--runtime-dir", str(tmp_path), "reconcile-loop", "--once"])
    assert code == 0
    report = json.loads(capsys.readouterr().out)
    assert "local" in report
    assert "chain" in report
    assert report["interval_seconds"] == 300


def test_run_loop_once_does_not_sleep(tmp_path):
    slept = []
    report = run_loop(
        interval=5,
        once=True,
        ledger=Ledger(tmp_path),
        sleep=slept.append,
        transport=lambda url, method, params: None,
    )
    assert slept == []
    assert "ran_at" in report
