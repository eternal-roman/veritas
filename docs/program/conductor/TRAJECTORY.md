# Trajectory — agent commerce vision

**Updated:** 2026-08-08T21:10:00Z (continuous cycle-5)
**Main:** `b253532`

## Where we are

| Layer | State |
|-------|--------|
| M7 credits/SIWx | **On main** — do not re-open |
| N0 notary | **On main** `4cd2d0c` (#30) |
| N1.1 EIP-191 attest | **On main** `db04ae2` (#33) |
| N1.2 free attest verify | **On main** `32d1054` (#34) |
| P7 re-fetch verify | **On main** `4697c8d` (#38) |
| N1.3 EvidencePack | **On main** `622429c` (#41) |
| cycle-1 dogfood | **On main** `2cbed44` (#44) |
| **G9-design reconcile** | **On main `6777a92` (#46)** — gap G9 still **open** |
| **N1.4 Merkle evidence log** | **On main `b253532` (#49)** |
| On-chain settlements | **0** |

## Primary trajectory

```
M7 → N0 → N1.1 → N1.2 → P7 → N1.3 → cycle-1 → G9-design → N1.4 DONE
  → Overseer NEXT (live RPC G9 dogfood | N1.5 anchors | cycle-5 | other)
```

**This-cycle bet:** none (claim free).

## Parked

- Re-opening N1.4 / G9-design / cycle-1 / N1.3 / P7 / N0 / N1.1 / N1.2 / M7 / O.8 as product NEXT
- Dual product claims
- Settlement fiction without tx hash
- Claiming G9 **closed** without live RPC evidence
- prefer_bet=N0 while N0 already on main (dual)

## Landmass

On-chain settlements: **0**. Multi-billion A2A hub: **L0 aspiration only**.
N1.4 proves operator-local Merkle inclusion for this instance's leaf list — not public CT, not on-chain anchor.
G9-design proves fail-closed chain-classify surface — not live confirmation.
