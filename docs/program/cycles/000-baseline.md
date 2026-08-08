# Cycle 000 — Baseline stock (main before the flywheel)

**Date:** 2026-08-08  
**Tree:** `main` @ `4c3b23c` (Money path, ops hardening, dogfood 2–4, receipt path fix)  
**Kind:** stock only — no code shipped in this cycle  
**PR:** n/a

## Scorecard (pre-loop)

| Axis | Score | Evidence | What blocks 4 |
|------|------:|----------|---------------|
| A — Buy alone | 2 | `payer.py` + `LocalAccountSigner` + L2 payment model (8,720 traces); dogfood cycle 2 local path | No unattended testnet settlement (Phase 0.1) |
| B — Sell alone | 2 | `veritas-agent up`, free-mode bootstrap, wallet keystore, MCP free tools | Funding, TLS, paid MCP, retention O.6, multi-instance |
| C — Money is real | 0 | Fail-closed facilitator client; ledger records *claims* of settlement | **0 on-chain settlements**; G9 no chain reconcile |
| D — Product worth | 1 | Honest snippets + refusal taxonomy; Serper tier (fixture-shaped) | No full-text; no notary (N0); no quality table vs baselines |
| E — Found alone | 1 | Self-traversing `/.well-known/x402`, `/llms.txt`, identity, constitution | No Bazaar/registry; no public host |
| F — Lifecycle compounds | 2 | Trust counters (paid-only scoring), metering, `veritas-ops`, dogfood 2–4 | Calibrator untrained; no attestations; no registry ranking |

**Sum:** 10 / 24. This is the floor the flywheel must beat.

## Excellence inventory (do not regress)

1. `unavailable` ≠ `no_evidence`; never bill for our failure.
2. One engine: all surfaces → `veritas.pipeline.run_research`.
3. Verify-before-work; deliver-fsync-before-settle; nonce claimed once.
4. Constitution articles L1-enforced or L0-aspirational — no middle fiction.
5. Exception text and payment headers stay off the wire and off the logs.
6. Dogfood cycles are CI-gated and have found real defects.

## Defect / program resume (from STATE.md)

**NEXT ACTION on baseline day:** O.6 — retention and `410 Gone` (≠ 404).  
Then O.8 (supply chain), M7 (credits/SIWx), Phase N0 (notary).

**Open product killers:** settlement proof, retrieval quality, public discovery,
shared multi-instance state, G9 chain reconciliation.

## Dogfood state

| Cycle | Status | Defects found |
|-------|--------|---------------|
| 1 cold install | blocked on N0 | — |
| 2 paying buyer | done | 1 (fixed) |
| 3 hostile caller | done | 1 (fixed) |
| 4 operator economics | done | 2 (fixed) |
| 5 ecosystem verify | blocked on standalone verifier | — |

## Reframe seed for cycle 001

Default bet: **O.6 retention / 410 Gone** — load-bearing for any production
serve, unblocks honest receipt lifecycle, raises axis B.

Allowed deviations if stock finds something more severe than unbounded disk:

- Regression of an L1 money-path invariant
- Security defect class of O17 (path traversal) severity
- Blocker that prevents the next dogfood cycle from being honest

## NOT PROVEN (carried forward)

- Any payment settled on-chain
- That a hostile external agent will pay for the current product
- That trust scores mean anything with only local traffic
- Multi-instance safety
- Hub / market / billion-dollar outcomes of any kind
