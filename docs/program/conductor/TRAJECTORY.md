# Trajectory — agent commerce vision

**Updated:** 2026-08-08T17:50:00Z (conductor 45m tick)  
**Main:** `a4cfc49`

## North star (L0 — never claim proven)

Substrate for **agent independence**, **hyper-scalable agent commerce**, and
**product lifecycle enrichment**. Dollar-scale hub outcomes are direction only.

## Where we are (measured)

| Layer | State |
|-------|--------|
| Honesty taxonomy / one engine / money-path order | On main (prior work) |
| O.6 retention + 410≠404 | **On main** `48194ab` |
| `/v1/verify` claim honesty (P7) | **On main** `4a3d105` |
| Buyer diligence + standalone verifier | **On main** `a4cfc49` |
| O.8 supply chain | **MID-FLIGHT** worktree `veritas-o8` / `feat/o.8-supply-chain` — uncommitted WIP (locks, SHA actions, SBOM, tests); **no PR yet** |
| M7 credits / N0 notary | Parked until O.8 PR lands |
| On-chain settlement | **0** (axis C) |

## Scorecard snapshot (honest)

| Axis | ~Level | Note |
|------|--------|------|
| A Buy alone | ~3 | Diligence + payer gate on main; still no testnet settle proof |
| B Sell alone | ~3 | Retention/410 + ops prune; multi-instance open |
| C Money real | 0 | No tx hash; G9 open |
| D Product worth | 1 | Snippets; N0 not started |
| E Found alone | 1 | Well-known only; no Bazaar |
| F Lifecycle | ~2–3 | Trust, metering, ops, diligence; supply-chain hardening in flight |

## Primary trajectory (this era)

```
O.8 supply chain  →  M7 credits  →  N0 notary / product worth
         │
         └── parallel only if outranked: G9 design (RPC), hostile pay tests
```

**This-cycle bet:** **O.8** — finish the mid-flight branch (commit → tests-green → PR, no merge).  
Do **not** open a second product bet.

## Parked (explicit)

- Dual product PRs / second O.8 cycle while `feat/o.8-supply-chain` is dirty  
- Scout seedlings as “approved dependencies”  
- Bazaar before settlement instrumentation  
- Claiming diligence closes on-chain risk  
- N0 / M7 until O.8 is on main or honestly parked with evidence  

## Conferral inputs honored

- Steward: cards realigned; primary O.8; no #18 BLOCKED theater  
- Overseer: ON_TASK; refuse parallel N0/M7  
- Scout: patterns only (SBOM/sign, payment gates, G9 harness)  
- Peer: IDLE  
- Flywheel: O.8 WIP present — **continue**, do not restart dual  

## Landmass (always)

Hostile external agent still cannot: discover a public host, settle on-chain
with us, or buy notary-grade product. Local green ≠ hub. On-chain settlements: **0**.
