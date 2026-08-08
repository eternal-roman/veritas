# Pruner CURRENT

- **Time:** 2026-08-08T21:15:00Z
- **Branch / HEAD:** `origin/main` @ **`db04ae2`** (N0 product via **#30** `4cd2d0c`; tip also has N1.1 #33 + integrity #29/#32)
- **Scope:** N0 Evidence Notary — `veritas/notary/*` (fetch/extract/record/license/robots/observe), pipeline `observe_urls` → one engine, `POST /v1/notarize` money path + inv.3 share of `_refund_unfinished_charge`, discovery/llms notarize line, tests `test_notary_*` + `test_notarize_api`
- **Verdict:** LEAN
- **ship_ok:** true
- **Deleted / pruned:** none this gate (N0 stays one observe path; no second engine/payer; no N1 Merkle/ZK/re-fetch in the N0 surface)
- **Refined:** notarize reuses research charge-publish / crash-refund helper (no forked refund path)
- **Battery:**
  - N0 surface (`test_notarize_api` + `test_notary_*` + sign): **93 passed**
  - full suite excl. dogfood/payment_model: **706 passed, 2 skipped** (local; mcp tool-set pin fixed for `verify_attestation`)
  - `ruff check veritas tests` (notary + server slice): **All checks passed**
  - harness: **exit 0** (unavailability honesty correct)
  - payment_model module: **8720 traces, I1–I7 holds**
  - PR #30 CI: Tests & syntax / Structure / Security / Package / Container / CodeQL **SUCCESS**
- **E2E exercised:** free + paid notarize paths in API tests; unavailable non-billable (no settle); credit debit + unexpected raise → refund (N0-J); SSRF/robots refuse non-billable; observe→pipeline route. Live facilitator settle / on-chain: **NOT PROVEN** (C=0)
- **Denied (will not ship):** second scraper/payer; shipping N0 without inv.3 parity; settlement success without tx; dual product NEXT while N0 was open
- **Directive:** N0 product is on main — claim free; sole authorized NEXT is **cycle-1 dogfood** (cold install). Do not re-open N0/M7 as NEXT.
- **PROPERTY / EVIDENCE / NOT PROVEN:**

```
PROPERTY: N0 notary core is lean and functioning on main: one observe engine,
          one payer, unavailable non-billable, inv.3 crash-refund on notarize;
          Pruner ship_ok for the landed #30 surface
EVIDENCE LEVEL: L1
CHECKED ARTIFACT: origin/main 4cd2d0c (#30); tip db04ae2; veritas/notary/*;
  veritas/server.py _notarize + _refund_unfinished_charge; tests/test_notarize_api.py
  (incl. unexpected failure refund); CI run 31274948468 SUCCESS; local 93 notary
  tests + harness + payment_model
ASSUMPTIONS: Single-instance ledger/credits; offline fixtures for fetch SSRF;
  mcp SDK present only when optional extra installed
NOT PROVEN: on-chain settlement (0); cold autonomous install (cycle-1);
  multi-instance; live facilitator notarize settle
```
