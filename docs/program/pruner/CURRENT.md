# Pruner CURRENT

- **Time:** 2026-08-08T20:30:00Z
- **Branch / HEAD:** `origin/main` @ `be03dcd` (M7 product via #23 `2171bfa` + #28 `386efff`)
- **Scope:** M7 surface — `veritas/credits.py`, `veritas/siwx.py`, server wire,
  `tests/test_credits*.py`, `tests/test_siwx.py`; STATE/claim closeout only
  (no new product code this ship)
- **Verdict:** LEAN
- **ship_ok:** true
- **Deleted / pruned:** none this tick (M7 already lean: one ledger, one SIWx
  store, no second payer/engine; top-up refuses free/misconfigured invent)
- **Refined:** n/a (verify-only)
- **Battery:**
  - `pytest tests/test_credits.py tests/test_siwx.py tests/test_credits_api.py`
    (+ discovery/errors): **68 passed**
  - full suite excl. dogfood/payment_model: **602 passed, 2 skipped**
  - dogfood: **5 passed**; payment_model tests: **7 passed**; module: **8720
    traces, I1–I7 holds**
  - `ruff check veritas tests`: **All checks passed**
  - harness: **exit 0** (unavailability honesty correct)
- **E2E exercised:** credit-paid research success debit; insufficient →
  `credits_insufficient`; unavailable + deadline + unexpected raise refund;
  top-up settled grants / failed+indeterminate refuse; SIWx challenge+verify
  offline; `X-PAYMENT` still wins when present. Live facilitator top-up:
  **NOT PROVEN**
- **Denied (will not ship):** re-implementing M7; second payer; settlement
  success claim without tx hash
- **Directive:** Plane may advance NEXT to **N0**. Do not dual-track M7.
- **PROPERTY / EVIDENCE / NOT PROVEN:**

```
PROPERTY: M7 credits/SIWx path is on main, battery green on exercised cases,
          refunds cover handled and unexpected failure; ship_ok for closeout
EVIDENCE LEVEL: L1
CHECKED ARTIFACT: origin/main be03dcd; #23 2171bfa; #28 386efff;
  tests/test_credits.py, test_siwx.py, test_credits_api.py; ruff; harness;
  payment_model I1–I7
ASSUMPTIONS: Single-instance SQLite credits/sessions; eth_account present for
  SIWx verify; no multi-instance ledger
NOT PROVEN: on-chain settlement (0); real facilitator top-up; multi-instance
  credit balance; N0 notary product
```
