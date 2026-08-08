# Trajectory — agent commerce vision

**Updated:** 2026-08-08T18:16:00Z (steward post-merge — #22 on main)  
**Main:** `96b9013`

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
| O.8 supply chain | **On main** `96b9013` (PR #22) — locks, SHA Actions, SBOM artifact, mcp pin. Docker hash-lock / signed SBOM **not** claimed |
| M7 credits / N0 notary | **NEXT = M7**; N0 parked until M7 lands or honest park |
| On-chain settlement | **0** (axis C) |

## Scorecard snapshot (honest)

| Axis | ~Level | Note |
|------|--------|------|
| A Buy alone | ~3 | Diligence + payer gate on main; still no testnet settle proof |
| B Sell alone | ~3 | Retention/410 + ops prune; multi-instance open |
| C Money real | 0 | No tx hash; G9 open |
| D Product worth | 1 | Snippets; N0 not started |
| E Found alone | 1 | Well-known only; no Bazaar |
| F Lifecycle | ~3 | Trust, metering, ops, diligence, **supply-chain pins on main** |

## Primary trajectory (this era)

```
O.8 supply chain (DONE 96b9013)  →  M7 credits  →  N0 notary / product worth
         │
         └── parallel only if outranked: G9 design (RPC), hostile pay tests
```

**This-cycle bet:** **M7** — credits via SIWx.  
Do **not** re-open O.8 or dual with N0.

## Parked (explicit)

- Re-litigating O.8 / second supply-chain PR without new defect evidence  
- Scout seedlings as “approved dependencies”  
- Bazaar before settlement instrumentation  
- Claiming diligence or locks close on-chain risk  
- N0 until M7 is on main or honestly parked with evidence  
- Image hash-lock / signed SBOM as separate follow-ons  

## Conferral inputs honored

- Steward: post-merge fog cleared; NEXT=M7  
- Overseer: ON_TASK; O.8 on main; freeze dual  
- Scout: anchors → M7; seedlings WATCH  
- Peer: IDLE  
- Flywheel: restart eligible for **M7** only  

## Landmass (always)

Hostile external agent still cannot: discover a public host, settle on-chain
with us, or buy notary-grade product. Local green ≠ hub. On-chain settlements: **0**.
