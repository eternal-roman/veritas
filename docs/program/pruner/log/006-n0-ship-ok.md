# Pruner log 006 — N0 Evidence Notary (G13)

**Time:** 2026-08-08T21:15:00Z  
**Claim:** N0 / `feat/n0-notary-core`  
**PR:** https://github.com/eternal-roman/veritas/pull/30 @ merge `4cd2d0c`

## Path

Post-merge gate confirmation + program closeout. Product already on main
with full CI SUCCESS; this log records ship_ok evidence.

## Findings

| Check | Result |
|-------|--------|
| Diff (N0) | +3163 focused notary + wire + tests |
| Second engine / payer | No — observe shared; `_refund_unfinished_charge` shared |
| inv.3 on notarize | Yes — charge publish + unexpected-failure test |
| unavailable non-billable | Yes — API tests |
| N1 scope | Held in #30 (N1.1 landed separately as #33) |
| CI #30 | All SUCCESS |
| Local N0 surface | 93 passed |
| harness / payment_model | exit 0 / I1–I7 holds |

## ship_ok

**true**
