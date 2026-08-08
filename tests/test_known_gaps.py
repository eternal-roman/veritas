"""Witnesses for the gaps the constitution registers as open.

Each test here pins **current, defective behaviour**. That is deliberate: the
constitution's register may only carry an open gap if a test proves the gap is
real, so the register cannot rot into a list of things someone once believed.

When a gap is fixed the corresponding test starts failing. That is the signal to
close the gap in `veritas/constitution.py` and delete the witness — not to patch
the test.
"""

from __future__ import annotations

from pathlib import Path

import pytest


def test_known_gap_settlements_are_never_checked_against_the_chain():
    """G9. The ledger records what the facilitator told us — including the
    entries where it told us nothing. No code re-checks any of it against an
    RPC endpoint, so `settled` means "we were told so", not "the chain
    agrees". An operator can state what this instance believes it earned, not
    what it holds.

    If this test fails, the gap has been fixed — close G9 and delete this test.
    """
    from veritas import ledger as ledger_module

    source = Path(ledger_module.__file__).read_text(encoding="utf-8")
    assert "eth_getTransactionReceipt" not in source
    assert not hasattr(ledger_module.Ledger, "reconcile_against_chain")


def test_known_gap_the_trust_score_is_self_reported():
    """G10. `/v1/trust` is computed by the graded party from its own records.
    A seller that simply logged favourable outcomes would produce an identical
    document, and nothing external attests to it. Restricting scoring to paid
    traffic (G7) raised the cost of manipulation; it did not make the number
    verifiable by the buyer relying on it.

    If this test fails, the gap has been fixed — close G10 and delete this
    test.
    """
    from veritas import trust

    source = Path(trust.__file__).read_text(encoding="utf-8")
    # An externally attested score would have to carry a signature from
    # someone other than us, or cite a third-party attestation it verified.
    assert "verify_attestation" not in source
    assert not hasattr(trust, "verify_external_attestation")
    # And the served score says plainly that it is our own word.
    assert "self_reported" in source


def test_known_gap_survival_reports_are_bounded_by_what_auditors_share():
    """G11. A survival report is a pure function of the records handed to it,
    and nothing forces an unfavourable record into the set: withholding the
    divergence an auditor observed yields a clean report from a curated
    subset. Divergence counts are a floor, never a ceiling.

    If this test fails, auditor-side publication the seller cannot filter
    exists — close G11 and delete this test.
    """
    pytest.importorskip("eth_account")
    from eth_account import Account

    from veritas.audit import perform_audit, survival_report
    from veritas.hashing import compute_content_hash
    from veritas.notary.fetch import FetchResult
    from veritas.notary.pack import build_evidence_pack
    from veritas.notary.sign import OperatorSigner, sign_evidence_record

    def fetch(body):
        def fake(request_url, **kwargs):
            return FetchResult(
                request_url=request_url, final_url=request_url, status=200,
                headers={"content-type": "text/plain"}, body=body, truncated=False,
            )
        return fake

    def signer():
        return OperatorSigner("0x" + bytes(Account.create().key).hex())

    body = "G11 witness body."
    seller = signer()
    fields = {
        "url": "https://example.org/g11",
        "content_hash": compute_content_hash(body),
        "observed_at": "2026-08-08T12:00:00Z",
        "extract_version": "extract.v1",
        "request_id": "req-g11",
    }
    pack = build_evidence_pack(
        **fields, attestation=sign_evidence_record(fields, seller)
    )
    robots = "User-agent: *\nAllow: /\n"
    confirmed = perform_audit(
        pack, signer=signer(), robots_body=robots,
        fetch_fn=fetch(body.encode("utf-8")),
    )
    diverged = perform_audit(
        pack, signer=signer(), robots_body=robots,
        fetch_fn=fetch(b"a different body entirely"),
    )

    honest = survival_report([confirmed, diverged])
    assert honest["verdict"] == "contested"
    # The gap: drop the unfavourable record and the report cannot tell.
    curated = survival_report([confirmed])
    assert curated["verdict"] == "surviving"
    assert curated["diverged_auditors"] == 0


# P7 closed: POST /v1/verify binds origin re-fetch (url+content_hash) and
# receipt re-fetch (request_id → store.load → re-fetch). See
# tests/test_refetch_verify.py. Legacy content+content_hash remains labeled
# binding: caller_supplied and is not claimed as independent.
