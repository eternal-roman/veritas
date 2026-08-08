"""veritas-audit: exit codes carry the verdict taxonomy out to the process."""

from __future__ import annotations

import json

import pytest
from eth_account import Account

from veritas.audit_cli import (
    EXIT_BAD_INPUT,
    EXIT_CONFIRMED,
    EXIT_DIVERGED,
    EXIT_UNOBSERVED,
    main,
)
from veritas.hashing import compute_content_hash
from veritas.notary.fetch import FetchError, FetchResult
from veritas.notary.pack import build_evidence_pack
from veritas.notary.sign import ENV_SIGNING_KEY, OperatorSigner, sign_evidence_record

pytest.importorskip("eth_account")

ROBOTS_OK = "User-agent: *\nAllow: /\n"
BODY = "CLI audit body."


def _key() -> str:
    return "0x" + bytes(Account.create().key).hex()


def _pack_file(tmp_path, name="pack.json"):
    seller = OperatorSigner(_key())
    fields = {
        "url": "https://example.org/cli",
        "content_hash": compute_content_hash(BODY),
        "observed_at": "2026-08-08T12:00:00Z",
        "extract_version": "extract.v1",
        "request_id": "req-cli-1",
    }
    pack = build_evidence_pack(
        **fields, attestation=sign_evidence_record(fields, seller)
    )
    path = tmp_path / name
    path.write_text(json.dumps(pack), encoding="utf-8")
    return path, pack


def _route_fetch(monkeypatch, body: bytes | None):
    """Route the CLI's live re-fetch through an offline fixture."""
    import veritas.audit as audit_mod

    real = audit_mod.refetch_verify

    def fake(url, expected, **kwargs):
        if body is None:
            def failing(request_url, **_kw):
                raise FetchError("connection refused", url=request_url)
            return real(url, expected, robots_body=ROBOTS_OK, fetch_fn=failing)

        def fetch_fn(request_url, **_kw):
            return FetchResult(
                request_url=request_url, final_url=request_url, status=200,
                headers={"content-type": "text/plain"}, body=body, truncated=False,
            )
        return real(url, expected, robots_body=ROBOTS_OK, fetch_fn=fetch_fn)

    monkeypatch.setattr(audit_mod, "refetch_verify", fake)


@pytest.fixture
def signed_env(monkeypatch):
    monkeypatch.setenv(ENV_SIGNING_KEY, _key())


def test_run_confirmed_exits_zero(tmp_path, monkeypatch, signed_env, capsys):
    path, _ = _pack_file(tmp_path)
    _route_fetch(monkeypatch, BODY.encode("utf-8"))
    assert main(["run", str(path)]) == EXIT_CONFIRMED
    record = json.loads(capsys.readouterr().out)
    assert record["verdict"] == "confirmed"
    assert "auditor" in record


def test_run_diverged_exits_one(tmp_path, monkeypatch, signed_env):
    path, _ = _pack_file(tmp_path)
    _route_fetch(monkeypatch, b"the origin changed")
    assert main(["run", str(path)]) == EXIT_DIVERGED


def test_run_unobserved_exits_two(tmp_path, monkeypatch, signed_env):
    path, _ = _pack_file(tmp_path)
    _route_fetch(monkeypatch, None)
    assert main(["run", str(path)]) == EXIT_UNOBSERVED


def test_run_invalid_pack_exits_three(tmp_path, monkeypatch, signed_env):
    path, pack = _pack_file(tmp_path)
    pack["content_hash"] = "sha256:" + "00" * 32
    path.write_text(json.dumps(pack), encoding="utf-8")
    assert main(["run", str(path)]) == EXIT_BAD_INPUT


def test_run_without_key_says_unsigned(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv(ENV_SIGNING_KEY, raising=False)
    monkeypatch.setenv("VERITAS_AGENT_DIR", str(tmp_path / "no_wallet"))
    path, _ = _pack_file(tmp_path)
    _route_fetch(monkeypatch, BODY.encode("utf-8"))
    assert main(["run", str(path)]) == EXIT_CONFIRMED
    record = json.loads(capsys.readouterr().out)
    assert "unsigned" in record
    assert "auditor" not in record


def test_verify_and_report_round_trip(tmp_path, monkeypatch, signed_env, capsys):
    path, _ = _pack_file(tmp_path)
    _route_fetch(monkeypatch, BODY.encode("utf-8"))
    assert main(["run", str(path)]) == EXIT_CONFIRMED
    record_path = tmp_path / "record.json"
    record_path.write_text(capsys.readouterr().out, encoding="utf-8")

    assert main(["verify", str(record_path)]) == EXIT_CONFIRMED
    verdict = json.loads(capsys.readouterr().out)
    assert verdict == {"valid": True, "reason": "ok"}

    assert main(["report", str(record_path), str(record_path)]) == EXIT_CONFIRMED
    report = json.loads(capsys.readouterr().out)
    assert report["distinct_auditors"] == 1
    assert report["verdict"] == "surviving"


def test_verify_tampered_record_exits_one(tmp_path, monkeypatch, signed_env, capsys):
    path, _ = _pack_file(tmp_path)
    _route_fetch(monkeypatch, BODY.encode("utf-8"))
    main(["run", str(path)])
    record = json.loads(capsys.readouterr().out)
    record["verdict"] = "diverged"
    record_path = tmp_path / "tampered.json"
    record_path.write_text(json.dumps(record), encoding="utf-8")
    assert main(["verify", str(record_path)]) == EXIT_DIVERGED
