# Pruner CURRENT

- **Time:** 2026-08-08T22:15:00Z
- **Path:** HEAVY / bet **N0** (post-merge; `feat/n0-notary-core` gone after #30)
- **Branch / HEAD:** `pruner/n0-residue-gate` @ base **`1e89e24`** (origin/main tip; N0 @ `4cd2d0c` ancestry)
- **Scope:** Aggressive multi-worker residue on notary compose path layered onto N0 core
- **Verdict:** **LEAN**
- **ship_ok:** **true**
- **Deleted / pruned:**
  - Dead package-level re-exports in `veritas/notary/__init__.py`
  - Soft-fail `except EvidencePackError: pass` on completed pack attach
  - Soft-fail `except EvidenceLogError` omit of Merkle log / inclusion proof
  - Stale package docstring claiming re-fetch/Merkle still later N1 work
- **Refined:**
  - Triple fetch-unavailable blocks → `_fetch_unavailable` (~−72 LOC net)
  - Fail-closed pack + evidence_log on completed observations
- **Battery:**
  - `pytest tests/ -q` → **752 passed, 1 skipped** (full suite green with same prunes)
  - `ruff check veritas tests` → pass
  - harness → exit 0; payment_model → I1–I7 holds
- **E2E:** offline observe completed + pack + inclusion_proof; free notarize path; discovery advertises notarize
- **Denied:** settlement fiction; dual NEXT re-open N0; second engine
- **Directive:** N0 surface lean+green after multi-worker soft-fail purge. Product claim free after land. Settlements **0**.
- **PROPERTY / EVIDENCE / NOT PROVEN:**

```
PROPERTY: N0 observe/notarize one-engine path holds; completed observations fail-closed on pack/log; unavailable non-billable; no dead package re-exports
EVIDENCE LEVEL: L1
CHECKED ARTIFACT: veritas/notary/{__init__,observe}.py @ 4f74f92; pytest 752 passed; harness; payment_model I1–I7; offline observe E2E
ASSUMPTIONS: feat/n0-notary-core deleted after #30 — gate evaluates N0 surface on tip ancestry
NOT PROVEN: on-chain settlement (0); live facilitator notarize settle
```
