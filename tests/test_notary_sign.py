"""N1.1: EIP-191 attestation of EvidenceRecord binding fields."""

from __future__ import annotations

import pytest
from eth_account import Account

from veritas.hashing import compute_content_hash
from veritas.notary.sign import (
    ENV_SIGNING_KEY,
    MESSAGE_VERSION,
    SCHEME,
    NotarySignError,
    OperatorSigner,
    canonical_attestation_message,
    maybe_attest_record,
    operator_signer_from_env,
    sign_evidence_record,
    verify_attestation,
)

pytest.importorskip("eth_account")


def _record(**overrides):
    body = "Observed body for N1.1 signing tests."
    base = {
        "url": "https://example.org/page",
        "observed_at": "2026-08-08T12:00:00Z",
        "content_hash": compute_content_hash(body),
        "body": body,
        "extract_version": "extract.v1",
        "media_kind": "text",
        "retention_class": "standard",
        "request_id": "req-n1-1",
    }
    base.update(overrides)
    return base


@pytest.fixture
def account():
    return Account.create()


@pytest.fixture
def signer(account):
    return OperatorSigner("0x" + bytes(account.key).hex())


def test_canonical_message_is_stable_and_versioned():
    msg = canonical_attestation_message(_record())
    assert msg.startswith(MESSAGE_VERSION)
    assert "url: https://example.org/page" in msg
    assert "content_hash: sha256:" in msg
    assert "request_id: req-n1-1" in msg


def test_sign_and_verify_round_trip(signer, account):
    record = _record()
    attestation = sign_evidence_record(record, signer)
    assert attestation["scheme"] == SCHEME
    assert attestation["signer"].lower() == account.address.lower()
    assert attestation["signature"].startswith("0x")
    assert "private" not in str(attestation).lower()
    assert bytes(account.key).hex() not in str(attestation).lower()
    ok, reason = verify_attestation(record, attestation, expected_signer=account.address)
    assert (ok, reason) == (True, "ok")


def test_tampered_content_hash_fails_verify(signer):
    record = _record()
    attestation = sign_evidence_record(record, signer)
    tampered = dict(record, content_hash="sha256:" + "00" * 32)
    ok, reason = verify_attestation(tampered, attestation)
    assert ok is False
    assert reason in ("signer_mismatch", "message_mismatch") or "fail" in reason or reason != "ok"


def test_wrong_expected_signer_fails(signer, account):
    record = _record()
    attestation = sign_evidence_record(record, signer)
    other = "0x" + "11" * 20
    ok, reason = verify_attestation(record, attestation, expected_signer=other)
    assert (ok, reason) == (False, "unexpected_signer")


def test_forged_signature_rejected(signer):
    record = _record()
    attestation = sign_evidence_record(record, signer)
    forged = dict(attestation, signature="0x" + "ab" * 65)
    ok, reason = verify_attestation(record, forged)
    assert ok is False


def test_malformed_key_refused():
    with pytest.raises(NotarySignError):
        OperatorSigner("not-a-key")
    with pytest.raises(NotarySignError):
        OperatorSigner("0x" + "zz" * 32)


def test_operator_signer_from_env_key(monkeypatch, account):
    key = "0x" + bytes(account.key).hex()
    monkeypatch.setenv(ENV_SIGNING_KEY, key)
    monkeypatch.delenv("VERITAS_AGENT_DIR", raising=False)
    resolved = operator_signer_from_env()
    assert resolved is not None
    assert resolved.address.lower() == account.address.lower()


def test_no_key_omits_attestation(monkeypatch):
    monkeypatch.delenv(ENV_SIGNING_KEY, raising=False)
    monkeypatch.setenv("VERITAS_AGENT_DIR", "definitely-missing-agent-dir-n11")
    assert operator_signer_from_env() is None
    assert maybe_attest_record(_record()) is None


def test_maybe_attest_record_signs_when_configured(monkeypatch, account):
    monkeypatch.setenv(ENV_SIGNING_KEY, "0x" + bytes(account.key).hex())
    attestation = maybe_attest_record(_record())
    assert attestation is not None
    ok, reason = verify_attestation(_record(), attestation, expected_signer=account.address)
    assert (ok, reason) == (True, "ok")


def test_observe_attaches_attestation_when_key_set(monkeypatch, account):
    from veritas.notary.fetch import FetchResult
    from veritas.notary.observe import observe

    monkeypatch.setenv(ENV_SIGNING_KEY, "0x" + bytes(account.key).hex())

    def fake_fetch(url, **kwargs):
        return FetchResult(
            request_url=url,
            final_url=url,
            status=200,
            headers={"content-type": "text/plain"},
            body=b"Hello from origin under signature.",
            truncated=False,
        )

    result = observe(
        "https://example.org/signed",
        request_id="obs-sign-1",
        robots_body="User-agent: *\nAllow: /\n",
        fetch_fn=fake_fetch,
        observed_at="2026-08-08T15:00:00Z",
    )
    assert result["status"] == "completed"
    assert "attestation" in result
    ok, reason = verify_attestation(
        result["evidence_record"],
        result["attestation"],
        expected_signer=account.address,
    )
    assert (ok, reason) == (True, "ok")
    chain_blob = str(result["custody_chain"])
    assert "attested" in chain_blob or "notary.sign" in chain_blob
    assert bytes(account.key).hex() not in chain_blob


def test_observe_omits_attestation_without_key(monkeypatch):
    from veritas.notary.fetch import FetchResult
    from veritas.notary.observe import observe

    monkeypatch.delenv(ENV_SIGNING_KEY, raising=False)
    monkeypatch.setenv("VERITAS_AGENT_DIR", "definitely-missing-agent-dir-n11")

    def fake_fetch(url, **kwargs):
        return FetchResult(
            request_url=url,
            final_url=url,
            status=200,
            headers={"content-type": "text/plain"},
            body=b"Unsigned observation body.",
            truncated=False,
        )

    result = observe(
        "https://example.org/unsigned",
        robots_body="User-agent: *\nAllow: /\n",
        fetch_fn=fake_fetch,
    )
    assert result["status"] == "completed"
    assert "attestation" not in result
