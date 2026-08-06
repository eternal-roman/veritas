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

    source = Path(ledger_module.__file__).read_text()
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

    source = Path(trust.__file__).read_text()
    # An externally attested score would have to carry a signature from
    # someone other than us, or cite a third-party attestation it verified.
    assert "verify_attestation" not in source
    assert not hasattr(trust, "verify_external_attestation")
    # And the served score says plainly that it is our own word.
    assert "self_reported" in source
