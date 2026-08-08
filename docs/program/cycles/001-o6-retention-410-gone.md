# Cycle 001 — O.6 retention / 410 Gone ≠ 404

**Date:** 2026-08-08  
**Tree:** `feat/o.6-retention-410-gone` @ `fe1d615` (O.6 code at `463e22f`)  
**Kind:** shippable bet (code + tests); PR open, CI green, **not merged**  
**PR:** https://github.com/eternal-roman/veritas/pull/18  
**Bet id:** O.6  
**Deviation from ladder:** no — matched STATE NEXT ACTION and stock killers

## Scorecard

| Axis | Before | After | Δ | Evidence / what still blocks 4 |
|------|-------:|------:|:-:|--------------------------------|
| A — Buy alone | 2 | 2 | 0 | Unchanged. Still offline `payer` + `LocalAccountSigner`; no unattended testnet pay→200 |
| B — Sell alone | 2 | **3** | **+1** | Retention window + ops prune + honest receipt lifecycle (`410`≠`404`). Still not 4: paid serve, auto re-register, funding, TLS, multi-instance |
| C — Money is real | 0 | 0 | 0 | **0 on-chain settlements**; G9 still open |
| D — Product worth | 1 | 1 | 0 | Snippets only; N0 not started |
| E — Found alone | 1 | 1 | 0 | Self-traversing discovery only; no Bazaar/public host |
| F — Lifecycle compounds | 2 | 2 | 0 | Trust + metering + ops CLI already; prune is incremental ops, not attestations/calibrator |

**Sum:** 10 → **11** / 24. Axis raised: **B** only. Not a landmass win — disk death is preventable; strangers still cannot buy or settle.

## Bet

**Title:** Retention/pruning with 410 Gone ≠ 404  
**Why now:** Receipts, ledger rows, and trust state grew without bound; disk was the first production failure mode. A pruned receipt must return **410 Gone** ("we deleted this"), not **404** ("never existed") — only 410 lets a buyer trust the receipt endpoint.  
**Non-goals (held):** multi-instance shared state (O6), G9 chain reconcile, L.2 receipt auth, N0 notary, M7 credits, O.8 supply chain.

### Acceptance (claimed L1)

| Criterion | Status | Where |
|-----------|--------|-------|
| Configurable retention window | met | `veritas/retention.py`, `VERITAS_RETENTION_DAYS` default 30 |
| Prune deletes/tombstones expired artifacts | met | `custody.ReceiptStore.prune`, `Ledger.prune` |
| `GET /v1/receipts/{id}` → 410 known-pruned, 404 never-seen | met | `veritas/server.py`, `ErrorCode.RECEIPT_GONE` |
| Deterministic prune tests | met | `tests/test_durability.py`, `tests/test_retention.py` |
| Ledger prune does not invent settlement outcomes | met | `tests/test_ledger.py` (indeterminate ≠ failed; no outcome rewrites) |
| Trust counters stay bounded | met (pre-existing O3) | one counter row; prune is a no-op for counters |
| Server wire 410 vs 404; no second engine/payment path | met | `tests/test_api.py::test_receipt_pruned_returns_410_gone_not_404` |

## Evidence

- **Code:** `veritas/retention.py` (new), `veritas/custody.py` (tombstones), `veritas/ledger.py` (`prune`), `veritas/errors.py` (`receipt_gone` @ 410), `veritas/server.py`, `veritas/ops_cli.py` (`veritas-ops prune`)
- **Tests (L1):**  
  - `tests/test_retention.py`  
  - `tests/test_durability.py` — expired→gone+tombstone; unexpired loadable; never-existed unknown; re-prune keeps tombstones  
  - `tests/test_api.py::test_receipt_pruned_returns_410_gone_not_404`  
  - `tests/test_errors.py::test_receipt_gone_is_registered_at_410`  
  - `tests/test_ledger.py` — aged settled/abandoned cascade delete; indeterminate untouched; no settlement outcome updates  
  - `tests/test_ops_cli.py` — JSON prune counts; rejects nonsense retention without mass delete  
- **CI:** all 7 checks SUCCESS on PR #18 head `fe1d615` (Tests, Structure, Security, Package, Container, CodeQL×2)  
- **Ship state:** branch pushed; `auto_merge=false`; **not on main** until human merges

## What still kills the product

1. **Zero on-chain settlements** — every commercial claim downstream is unproven  
2. **Snippet-grade retrieval** — notary (N0) and full-text extraction not built  
3. **No public host / TLS / Bazaar** — strangers cannot discover or reach the service  
4. **No multi-instance shared ledger/receipts (O6)** — balancer-unsafe replay and receipt 404s  
5. **G9** — `settled` means the facilitator said so; no chain RPC reconciliation  
6. **P7** — `/v1/verify` re-hashes caller input; no source binding  
7. **L6** — buyer queries persisted forever and served unauthenticated  
8. **Unattended buyer testnet pay→200 never executed** — `LocalAccountSigner` is offline EIP-712 only  

Closed this cycle as a *killer shape* (not as proof of production): **unbounded retention** — prune + tombstones exist and are L1-tested; ops must still *run* prune (not auto on every request).

## Proposed next bet

**O.8 — supply chain:** lockfile with hashes, SHA-pinned GitHub Actions, SBOM; bandit already at `-ll`.  
Then **M7** (credits via SIWx), then **Phase N0** (notary).  

Blocked outside sandbox (do not fake): G9 needs RPC; X1/X3/X6 need facilitator egress; dogfood cycle 1 gated on N0; cycle 5 on standalone verifier.

## PROPERTY / EVIDENCE (adversarial-code-truth)

```
PROPERTY: Expired receipts are tombstoned and served as 410 receipt_gone;
          never-seen ids stay 404 receipt_not_found; ledger prune deletes
          only aged settled/abandoned rows and never rewrites settlement
          outcomes (indeterminate remains ≠ failed)
EVIDENCE LEVEL: L1
CHECKED ARTIFACT: veritas/retention.py; veritas/custody.py prune/tombstone;
                  veritas/ledger.py prune; veritas/server.py receipt path;
                  tests/test_retention.py; tests/test_durability.py;
                  tests/test_api.py::test_receipt_pruned_returns_410_gone_not_404;
                  tests/test_ledger.py prune suite; PR #18 CI SUCCESS @ fe1d615
ASSUMPTIONS: ops schedules veritas-ops prune (no background janitor);
             single-instance filesystem + SQLite; retention days in [1, 3650]
NOT PROVEN: multi-instance shared prune/tombstones; live production disk
            under real traffic; on-chain settlement; that buyers will trust
            410 without receipt auth (L.2); merge of #18 onto main
```

## NOT PROVEN (carried forward)

- Any payment settled on-chain  
- Hostile external agent will pay for the current product  
- Trust scores mean anything beyond local traffic  
- Multi-instance safety  
- Hub / market / revenue outcomes of any kind  
- That PR #18 is on `main` (CI green ≠ merged)
