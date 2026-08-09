# Ecosystem Advance — discovery + cooperative track agents

**Status:** active plane (T4 research / substrate tracks) — **v2 mesh optimized**.  
**Does not dual product NEXT.** Overseer remains singular strategy gate.  
**Does not invent on-chain x402 settlement.** Product settlements remain **0**
until Phase 0.1 is proven. Local **plane money** is explicitly *not* that.

## Discovery (what is missing for A2A commerce scale)

| Track ID | Gap | Outcome until resolved |
|----------|-----|------------------------|
| **money_loop** | Live settle + G9; interim **plane token** for agent↔agent plane commerce | Agents can pay each other in local VAAT; product money path still honest |
| **multiparty_trust** | G10/G11/G12; third-party auditors | Standing not seller-curated; auditor publication |
| **product_worth** | Volume-worthy goods / measurable quality | Buyers retain; not snippet theater |
| **discovery_density** | How agents find sellers at density | Registry / density metrics after pay is not a trap |
| **multi_tenant** | Shared ledger/receipts across instances | Balancer-safe ops |
| **legal_identity** | Plane **visa** (network identity); KYA-style | Agents hold portable plane credentials |
| **network_effects** | Multi-seller / embed substrate | Ecosystem math, not single-shop |

### GitHub pattern sources (WATCH — not auto-adopt)

| Domain | Examples to harvest |
|--------|---------------------|
| Agent identity / KYA | SPIFFE/SPIRE, Entra agent identity, DID+VC agents, in-tree SIWx |
| Agent wallets | agent-wallet topics, spend-limit SDKs, x402 multi-sig |
| Multi-agent ledgers | Hash-chained journals; in-tree `veritas.credits` + `agent_money` |
| Discovery | MCP registries, A2A directories, well-known x402 |
| Multi-tenant | Shared store patterns; lease-based nonces |

## Org chart

```
                         OVERSEER (strategy gate)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         CONFERRAL      ECOSYSTEM BUS    track CURRENT/*
              │
         MESH RUNNER (offline cycle kernel) ← scale heartbeat
              │
    T4 tracks + Unblock Agent (when human ops gate money)
              │ proposals only
    CONDUCTOR / FLYWHEEL (one product NEXT) → PRUNER
```

| Rule | Detail |
|------|--------|
| **Overseer** | Accepts / holds / kills track proposals; may set prefer_track |
| **Tracks** | Loop until `resolved` or Overseer `parked` |
| **Mesh Runner** | Executes cycles offline so progress is not stuck on LLM ticks |
| **Plane money** | `veritas.agent_money` VAAT — never written as x402 settle |
| **Plane visa** | `veritas.agent_identity` |
| **Product claim** | Still one flywheel-claim |

## v2 scale (after 5-cycle optimize)

**Stuck found:** tick prompts without an executor → cycles stayed 0.  
**Fix:**

```bash
python -m veritas.plane_bootstrap
python -m veritas.ecosystem_cycle --cycles 5
```

| Rule | Detail |
|------|--------|
| **Bottleneck rank** | weight × (1 − progress); discovery_density low until money |
| **VAAT tax** | 1 VAAT per track per cycle → overseer |
| **LEARN every 5** | `ecosystem/learn/NNN-mesh-optimize.md` |
| **LLM fan-out** | Deep research only for top-3 ranked tracks |
| **Unblock Agent** | Human-ops checklist when money_loop #1 but RPC/wallet missing |
| **Scale** | Raise `--cycles` or schedule Mesh Runner; never dual product NEXT |

## Unblock-only mode (workflow hygiene §3)

**When:** mesh ranks **money_loop** high **and** product `VERITAS_RPC_URL` is
unset (or funded wallet missing).

| Active | Parked / quiet |
|--------|----------------|
| **Unblock** — `python -m veritas.unblock_probe` → `ecosystem/unblock/CHECKLIST.md` | Extra TRACK charter edits |
| Mesh kernel offline cycles (no PR required) | New mesh feature code without a buyer path |
| Optional human funding steps | Dual continuous workflows |

Product flywheel/implement stays **idle** until checklist required rows are
ready **or** Overseer names an explicit non-money singular bet
(`WORKFLOW_HYGIENE.md` §4). Plane VAAT ≠ product settle.

## Paths

| Artifact | Path |
|----------|------|
| Charter | `docs/program/ECOSYSTEM_ADVANCE.md` |
| Bus | `docs/program/ecosystem/BUS.md` |
| Conferral | `docs/program/ecosystem/OVERSEER_CONFERRAL.md` |
| Mesh Runner | `TRACK_MESH_RUNNER.md` + `veritas/ecosystem_cycle.py` |
| Unblock | `TRACK_UNBLOCK.md` + `TRACK_UNBLOCK_TICK_PROMPT.md` |
| Unblock probe | `veritas/unblock_probe.py` → `ecosystem/unblock/CHECKLIST.md` |
| Workflow hygiene | `WORKFLOW_HYGIENE.md` (idle · one hygiene PR · Unblock · dual continuous ban) |
| Plane money | `veritas/agent_money.py` |
| Plane visa | `veritas/agent_identity.py` |

```
PROPERTY: cooperative track plane + mesh kernel; Unblock-only when money blocked; no dual product NEXT; no fake settlement
EVIDENCE LEVEL: L0 (direction) + L1 (plane money/visa/cycle/probe tests)
NOT PROVEN: billion-dollar EV; product on-chain settle; G10–G12 closed
```
