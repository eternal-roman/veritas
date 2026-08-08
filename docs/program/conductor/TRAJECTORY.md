# Trajectory — agent commerce vision

**Updated:** 2026-08-08T21:05:00Z (conductor continuous cycle 6)
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
| G9-design reconcile | **On main** `6777a92` (#46) — gap G9 still open |
| **N1.4 Merkle log** | **On main `b253532` (#49)** — operator-local only |
| On-chain settlements | **0** |

## Primary trajectory

```
M7 → N0 → N1.1 → N1.2 → P7 → N1.3 → cycle-1 → G9-design → N1.4 DONE
  → cycle-5 ecosystem dogfood (THIS NEXT)
  → live-RPC G9 dogfood (parked; needs egress)
```

**This-cycle bet:** **cycle-5 ecosystem dogfood**

## Parked

- Re-opening N1.4 / G9-design / cycle-1 / N1.3 / P7 / N0 / N1.1 / N1.2 / **M7** / O.8
- Stale `prefer_bet=M7` hard-defaults
- Dual product claims
- Settlement fiction without tx hash
- Live RPC G9 close (needs egress)
- Public transparency log / on-chain anchors (N1.4 is operator-local only)

## Landmass

On-chain settlements: **0**. Multi-billion A2A hub: **L0 aspiration only**.
N1.4 proves operator-local inclusion proofs — not public CT, not chain.
