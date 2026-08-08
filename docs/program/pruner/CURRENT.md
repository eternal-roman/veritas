# Pruner CURRENT

- **Time:** 2026-08-08T21:20:00Z
- **Branch / HEAD:** `origin/main` @ **`32d1054`** (N1.2 #34; N1.1 #33; **N0 #30** `4cd2d0c`)
- **Scope:** N0 Evidence Notary gate (G13) — `veritas/notary/*`, pipeline
  `observe_urls` → one engine, `POST /v1/notarize` + inv.3 share of
  `_refund_unfinished_charge`, discovery/llms, tests `test_notary_*` +
  `test_notarize_api`. Post-merge confirmation on tip.
- **Verdict:** LEAN
- **ship_ok:** true
- **Deleted / pruned:** none (N0 remains one observe path; no second
  engine/payer; N1.1/N1.2 are optional attestation, not a second money path)
- **Refined:** notarize reuses research crash-refund helper
- **Battery:**
  - PR #30 CI: Tests & syntax / Structure / Security / Package / Container /
    CodeQL **SUCCESS** (merge commit `4cd2d0c`)
  - Local N0 surface: **93 passed** (notary + notarize + sign)
  - harness: **exit 0**; payment_model module: **I1–I7 holds**
- **E2E exercised:** paid/free notarize; unavailable non-billable; credit
  unexpected-failure refund (N0-J); SSRF/robots refuse. On-chain: **NOT PROVEN**
- **Denied:** re-open N0 as NEXT; second scraper/payer; settlement without tx
- **Directive:** N0 product ship gate passed. Claim free. Do not re-open N0/M7.
- **PROPERTY / EVIDENCE / NOT PROVEN:**

```
PROPERTY: N0 notary core is lean and functioning on main; Pruner ship_ok
EVIDENCE LEVEL: L1
CHECKED ARTIFACT: 4cd2d0c (#30); tip 32d1054; veritas/notary/*;
  server _notarize + _refund_unfinished_charge; CI SUCCESS on #30
ASSUMPTIONS: single-instance ledger/credits; offline SSRF fixtures
NOT PROVEN: on-chain settlement (0); cold install cycle-1
```
