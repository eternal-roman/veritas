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

# G9 closed: Ledger.reconcile_against_chain — tests/test_chain_reconcile.py
# G10 closed: independent audits — tests/test_durability.py
# G11 closed: publication-bound survival — tests/test_audit.py


def test_known_gap_warranty_bonds_are_commitments_not_escrow():
    """G12. A fired challenge indicates a forfeit, but no code escrows or
    settles a bond — the stake is an EIP-191 commitment, stated on the wire
    as bond_binding: signed_commitment_not_escrow. Until W1 (gated on Phase
    0 settlement proof), the unomittable-negative-reputation property of
    forfeits is designed, not real.

    If this test fails, escrowed bonds exist — close G12 and delete this
    test.
    """
    from veritas import warranty as warranty_module

    source = Path(warranty_module.__file__).read_text(encoding="utf-8")
    assert "signed_commitment_not_escrow" in source
    assert "escrow_bond" not in source
    assert not hasattr(warranty_module, "settle_forfeit")





# P7 closed: POST /v1/verify binds origin re-fetch (url+content_hash) and
# receipt re-fetch (request_id → store.load → re-fetch). See
# tests/test_refetch_verify.py. Legacy content+content_hash remains labeled
# binding: caller_supplied and is not claimed as independent.
