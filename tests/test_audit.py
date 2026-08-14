"""Survival records: independent audit of evidence attestations (A26).

The three constitution pointers live here:
`test_unobserved_never_counts_for_or_against_a_seller`,
`test_self_audit_is_excluded_from_independence_counts`,
`test_record_volume_from_one_key_counts_as_one_auditor`.
"""

from __future__ import annotations

import pytest
from eth_account import Account

from veritas.audit import (
    AUDIT_VERSION,
    VERDICT_CONFIRMED,
    VERDICT_DIVERGED,
    VERDICT_UNOBSERVED,
    AuditError,
    canonical_audit_message,
    is_self_audit,
    perform_audit,
    survival_report,
    verify_audit_record,
)
from veritas.hashing import compute_content_hash
from veritas.notary.fetch import FetchError, FetchResult
from veritas.notary.pack import build_evidence_pack
from veritas.notary.sign import OperatorSigner, sign_evidence_record, verify_attestation

pytest.importorskip("eth_account")

ROBOTS_OK = "User-agent: *\nAllow: /\n"
BODY = "Attested page body for survival-record tests."


def _signer():
    return OperatorSigner("0x" + bytes(Account.create().key).hex())


def _fetch(body: bytes):
    def fake_fetch(request_url, **kwargs):
        return FetchResult(
            request_url=request_url,
            final_url=request_url,
            status=200,
            headers={"content-type": "text/plain"},
            body=body,
            truncated=False,
        )

    return fake_fetch


def _failing_fetch(request_url, **kwargs):
    raise FetchError("connection refused", url=request_url)


def _pack(seller: OperatorSigner | None = None, body: str = BODY):
    fields = {
        "url": "https://example.org/attested",
        "content_hash": compute_content_hash(body),
        "observed_at": "2026-08-08T12:00:00Z",
        "extract_version": "extract.v1",
        "request_id": "req-audit-1",
    }
    attestation = sign_evidence_record(fields, seller) if seller else None
    return build_evidence_pack(**fields, attestation=attestation)


def _audit(pack, auditor, fetch_body: bytes | None = BODY.encode("utf-8")):
    fetch_fn = _fetch(fetch_body) if fetch_body is not None else _failing_fetch
    return perform_audit(
        pack, signer=auditor, robots_body=ROBOTS_OK, fetch_fn=fetch_fn
    )


# --- perform_audit -----------------------------------------------------------


def test_audit_of_intact_origin_is_confirmed_and_verifiable():
    seller, auditor = _signer(), _signer()
    record = _audit(_pack(seller), auditor)
    assert record["verdict"] == VERDICT_CONFIRMED
    assert record["attested_signer"] == seller.address.lower()
    ok, reason = verify_audit_record(record)
    assert (ok, reason) == (True, "ok")
    assert not is_self_audit(record)


def test_changed_origin_is_diverged_not_fraud():
    record = _audit(_pack(_signer()), _signer(), fetch_body=b"the page moved on")
    assert record["verdict"] == VERDICT_DIVERGED
    assert record["reason"] == "diverged"
    # The record itself carries the boundary: divergence, never fraud proof.
    assert "not" in record["note"] and "fraud" not in record["verdict"]
    ok, _ = verify_audit_record(record)
    assert ok


def test_unreachable_origin_is_unobserved():
    record = _audit(_pack(_signer()), _signer(), fetch_body=None)
    assert record["verdict"] == VERDICT_UNOBSERVED
    ok, _ = verify_audit_record(record)
    assert ok


def test_invalid_pack_cannot_be_audited():
    pack = _pack(_signer())
    pack["content_hash"] = "sha256:" + "00" * 32  # break pack_hash binding
    with pytest.raises(AuditError, match="pack_invalid"):
        _audit(pack, _signer())


def test_unattested_pack_audits_with_empty_seller():
    record = _audit(_pack(seller=None), _signer())
    assert record["attested_signer"] == ""
    assert record["verdict"] == VERDICT_CONFIRMED


# --- verify_audit_record -----------------------------------------------------


def test_tampered_record_fails_with_stable_reason():
    record = _audit(_pack(_signer()), _signer())
    flipped = dict(record)
    flipped["verdict"] = (
        VERDICT_DIVERGED if record["verdict"] == VERDICT_CONFIRMED else VERDICT_CONFIRMED
    )
    ok, reason = verify_audit_record(flipped)
    assert not ok
    assert reason == "message_mismatch"


def test_unsigned_record_is_invalid():
    record = perform_audit(
        _pack(_signer()),
        signer=None,
        robots_body=ROBOTS_OK,
        fetch_fn=_fetch(BODY.encode("utf-8")),
    )
    ok, reason = verify_audit_record(record)
    assert (ok, reason) == (False, "auditor_missing")


def test_wrong_version_is_invalid():
    record = _audit(_pack(_signer()), _signer())
    record["audit_version"] = "veritas-audit-record-v0"
    ok, reason = verify_audit_record(record)
    assert (ok, reason) == (False, "version_mismatch")


def test_audit_signature_is_domain_separated_from_evidence_attestation():
    """A signature over an audit message must never verify as an evidence
    attestation: same key family, disjoint message spaces."""
    seller, auditor = _signer(), _signer()
    record = _audit(_pack(seller), auditor)
    assert canonical_audit_message(record).startswith(AUDIT_VERSION)
    masquerade = {
        "url": record["url"],
        "content_hash": record["content_hash"],
        "observed_at": record["audited_at"],
        "extract_version": "extract.v1",
        "request_id": "",
    }
    ok, _reason = verify_attestation(masquerade, record["auditor"])
    assert not ok


# --- survival_report ---------------------------------------------------------


def test_unobserved_never_counts_for_or_against_a_seller():
    """A26. An origin nobody could observe is evidence of nothing: reported,
    never scored — the audit-layer form of unavailable != no_evidence."""
    seller = _signer()
    pack = _pack(seller)
    unobserved = [_audit(pack, _signer(), fetch_body=None) for _ in range(3)]
    report = survival_report(unobserved)
    assert report["unobserved_reported"] == 3
    assert report["countable_records"] == 0
    assert report["confirmed_auditors"] == 0
    assert report["diverged_auditors"] == 0
    assert report["verdict"] == "unaudited"

    # And mixed in, they change nothing that a confirmed audit established.
    confirmed = _audit(pack, _signer())
    held = [confirmed, *unobserved]
    with_noise = survival_report(held, publication=held)
    assert with_noise["verdict"] == "surviving"
    assert with_noise["confirmed_auditors"] == 1
    assert with_noise["unobserved_reported"] == 3


def test_self_audit_is_excluded_from_independence_counts():
    """A26. The attesting key auditing itself is a consistency check, not
    standing: surfaced in the counts, excluded from independence."""
    seller = _signer()
    record = _audit(_pack(seller), seller)  # seller audits its own claim
    assert is_self_audit(record)
    report = survival_report([record])
    assert report["self_audits_excluded"] == 1
    assert report["distinct_auditors"] == 0
    assert report["verdict"] == "unaudited"


def test_record_volume_from_one_key_counts_as_one_auditor():
    """A26. Two thousand records signed by one key are one witness — the
    same independence rule support.py applies to registrable domains."""
    seller, auditor = _signer(), _signer()
    pack = _pack(seller)
    records = [_audit(pack, auditor) for _ in range(5)]
    report = survival_report(records, publication=records)
    assert report["n_records"] == 5
    assert report["distinct_auditors"] == 1
    assert report["confirmed_auditors"] == 1
    assert report["verdict"] == "surviving"


def test_divergence_from_any_auditor_marks_contested():
    seller = _signer()
    pack = _pack(seller)
    confirmed = _audit(pack, _signer())
    diverged = _audit(pack, _signer(), fetch_body=b"changed underneath")
    report = survival_report([confirmed, diverged])
    assert report["confirmed_auditors"] == 1
    assert report["diverged_auditors"] == 1
    assert report["verdict"] == "contested"


def test_invalid_records_are_excluded_not_scored():
    seller = _signer()
    record = _audit(_pack(seller), _signer())
    forged = dict(record)
    forged["verdict"] = VERDICT_DIVERGED  # signature no longer matches
    held = [record, forged, {}]
    report = survival_report(held, publication=held)
    assert report["invalid_excluded"] == 2
    assert report["diverged_auditors"] == 0
    assert report["verdict"] == "surviving"


def test_no_publication_cannot_claim_surviving():
    seller = _signer()
    record = _audit(_pack(seller), _signer())
    report = survival_report([record])
    assert report["verdict"] == "unpublished"


def test_withheld_publication_is_curated():
    seller = _signer()
    pack = _pack(seller)
    confirmed = _audit(pack, _signer())
    diverged = _audit(pack, _signer(), fetch_body=b"changed underneath")
    report = survival_report([confirmed], publication=[confirmed, diverged])
    assert report["verdict"] == "curated"
    assert report["withheld_published"] == 1


def test_seller_filter_excludes_foreign_records():
    seller_a, seller_b, auditor = _signer(), _signer(), _signer()
    record_a = _audit(_pack(seller_a), auditor)
    record_b = _audit(_pack(seller_b), auditor)
    report = survival_report([record_a, record_b], seller=seller_a.address)
    assert report["foreign_excluded"] == 1
    assert report["countable_records"] == 1
    assert report["seller"] == seller_a.address.lower()
