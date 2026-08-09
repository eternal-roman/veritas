# Unblock Agent (human-ops gate for money path)

**Binding law:** [`WORKFLOW_HYGIENE.md`](WORKFLOW_HYGIENE.md) §3–4.  
**Tick prompt:** [`TRACK_UNBLOCK_TICK_PROMPT.md`](TRACK_UNBLOCK_TICK_PROMPT.md).  
**Living checklist:** [`ecosystem/unblock/CHECKLIST.md`](ecosystem/unblock/CHECKLIST.md)
(created/updated by probe).

Spawned when **money_loop** is ranked #1 (or product money is the bottleneck)
and Phase **0.1 / G9** cannot advance because operator credentials/egress are
missing. While that holds, Unblock is the **only active track** — other
ecosystem tracks stay mesh-offline or noop; **no new charters**.

| Role | Owns | Does not own |
|------|------|--------------|
| **Unblock** | Living checklist, honest env/network probes, confer when ready | Spending real funds without human; inventing settle; product claim; dual NEXT |

## Probe (preferred every Unblock tick)

```bash
python -m veritas.unblock_probe
```

Updates `docs/program/ecosystem/unblock/CHECKLIST.md` **in place**.  
**Do not open a docs PR** solely to rewrite the checklist unless a **required**
row flips (unknown→yes/no) with new evidence.

## Checklist (required for Phase 0.1 dogfood)

| Item | Source |
|------|--------|
| `VERITAS_RPC_URL` set + chain responds | probe |
| Facilitator URL reachable | probe (`VERITAS_FACILITATOR_URL` / `X402_FACILITATOR_URL`) |
| Wallet key configured | probe (env set only; never echo secrets) |
| Funded testnet wallet + test USDC | **human** confirmation |
| Public TLS host | optional |
| PyPI trusted publisher | optional / human ops |

When **required automated** rows are **yes** and human confirms funding → one
line to `ecosystem/OVERSEER_CONFERRAL.md`: recommend singular product NEXT =
Phase 0.1 / G9 dogfood. Overseer/Conductor own claim; Unblock does not set it.

## Forbidden

- Claiming on-chain settlement success
- Treating VAAT / plane money as product settle
- Opening restock/hygiene PRs (that is Steward/Conductor under §1–2)
- New mesh product features “while waiting for RPC”

```
PROPERTY: unblock agent surfaces human gates without fake green
EVIDENCE LEVEL: L1 (checklist + env/http probes) / L0 (funding readiness)
NOT PROVEN: on-chain settlement success
```
