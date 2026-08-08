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


def test_known_gap_the_verify_endpoint_is_circular():
    """P7. `POST /v1/verify` takes both the content and the hash from the
    caller, hashes the content, and reports whether they match. The caller
    supplied both sides, so the answer is arithmetic they could have done
    themselves — and asking us routes the check entirely through our goodwill,
    which is the opposite of what a verification endpoint is for. A dishonest
    server answers `valid: true` and nothing detects it.

    Nothing binds the content to a source: the endpoint never re-fetches the
    URL, never consults a stored receipt, and never checks the hash against
    anything this service previously published. It cannot distinguish a hash
    we issued from one the caller invented a moment ago.

    If this test fails, the gap has been fixed — close P7 and delete this test.
    Closing it means binding verification to something the caller does not
    control: a re-fetch of the source, or a lookup against the custody records
    we actually issued (ROADMAP N1.4).
    """
    from fastapi.testclient import TestClient

    from veritas import server as server_module
    from veritas.hashing import compute_content_hash
    from veritas.server import app

    client = TestClient(app)
    invented = "text this service has never seen, from no source at all"
    fabricated_hash = compute_content_hash(invented)

    response = client.post(
        "/v1/verify",
        json={"content": invented, "content_hash": fabricated_hash},
    )

    assert response.status_code == 200
    # The witness: a hash we never issued, over content we never retrieved,
    # is reported valid — because the endpoint only compares the caller's two
    # inputs to each other.
    assert response.json()["valid"] is True

    # And the served module never binds verification to anything the caller
    # does not control.
    source = Path(server_module.__file__).read_text(encoding="utf-8")
    verify_body = source.split('@app.post("/v1/verify")')[1].split("@app.")[0]
    assert "store.load" not in verify_body, "verify now consults stored receipts"
    assert "fetch" not in verify_body, "verify now re-fetches the source"
