# Mesh LEARN after 5 cycles

## Stuck diagnosis (pre-kernel)

| Stuck | Cause | Fix |
|-------|-------|-----|
| Cycles stayed 0 | Tick prompts without executor | `veritas.ecosystem_cycle` |
| 7 agents idle | No heartbeat / stipend loop | bootstrap + VAAT tax |
| Discovery thrash risk | Equal weight all tracks | Bottleneck weights |
| Overseer no marks | Empty BUS | Kernel rewrites BUS |

## Ranking after cycle 5

`product_worth > multiparty_trust > money_loop > multi_tenant > network_effects > legal_identity > discovery_density`

## Track cycles

| Track | Cycle | Status |
|-------|-------|--------|
| `money_loop` | 6 | open |
| `multiparty_trust` | 5 | open |
| `product_worth` | 5 | open |
| `legal_identity` | 6 | open |
| `multi_tenant` | 5 | open |
| `network_effects` | 5 | open |
| `discovery_density` | 5 | open |

## Evolution rules (v2)

1. **Execute offline first** — LLM ticks optional; kernel guarantees progress.
2. **Rank by bottleneck** — weight × (1 - progress); discovery low until money.
3. **Pay for work** — VAAT tax makes coordination auditable.
4. **Scale mesh not dual NEXT** — more track cycles ≠ product claim.
5. **Every 5 cycles** — Optimizer-style LEARN (this file); raise weights if stuck.

## Scale levers

| Lever | Action |
|-------|--------|
| Throughput | `python -m veritas.ecosystem_cycle --cycles N` |
| Fan-out | Parallel LLM ticks for top-3 ranked only |
| New agent | **Mesh Runner** (this kernel) + optional **Unblock Agent** for human ops checklist |
| Product gate | Still Overseer HOLD for x402 until RPC |

## Bootstrap snapshot

```json
{
  "visa_count": 13,
  "not_x402": true
}
```

```
PROPERTY: mesh advanced 5 cycles without dual product NEXT or fake settlement
EVIDENCE LEVEL: L1 (kernel + journal)
NOT PROVEN: track resolved; product settle; $1B EV
```
