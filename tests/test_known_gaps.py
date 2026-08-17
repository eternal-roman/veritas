"""Witnesses for the gaps the constitution registers as open.

Each test here pins **current, defective behaviour**. That is deliberate: the
constitution's register may only carry an open gap if a test proves the gap is
real, so the register cannot rot into a list of things someone once believed.

When a gap is fixed the corresponding test starts failing. That is the signal to
close the gap in `veritas/constitution.py` and delete the witness — not to patch
the test.
"""

from __future__ import annotations

# G9 closed: Ledger.reconcile_against_chain — tests/test_chain_reconcile.py
# G10 closed: independent audits — tests/test_durability.py
# G11 closed: publication-bound survival — tests/test_audit.py
# G12 closed: escrow_bond + settle_forfeit — tests/test_escrow.py





# P7 closed: POST /v1/verify binds origin re-fetch (url+content_hash) and
# receipt re-fetch (request_id → store.load → re-fetch). See
# tests/test_refetch_verify.py. Legacy content+content_hash remains labeled
# binding: caller_supplied and is not claimed as independent.
