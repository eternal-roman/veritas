# Ecosystem Advance — discovery + cooperative track agents

**Status:** active plane (T4 research / substrate tracks).
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
| Multi-agent ledgers | Hash-chained journals; in-tree eritas.credits + gent_money |
| Discovery | MCP registries, A2A directories, well-known x402 |
| Multi-tenant | Shared store patterns; lease-based nonces |

## Org chart

`
                         OVERSEER (strategy gate)
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         CONFERRAL      ECOSYSTEM BUS    track CURRENT/*
              │
    T4 Ecosystem tracks (research + plane code; cooperative)
    money_loop · multiparty_trust · product_worth
    discovery_density · multi_tenant · legal_identity · network_effects
              │ proposals only
    CONDUCTOR / FLYWHEEL (one product NEXT) → PRUNER
`

| Rule | Detail |
|------|--------|
| **Overseer** | Accepts / holds / kills track proposals; may set prefer_track |
| **Tracks** | Loop until 
esolved or Overseer parked |
| **Plane money** | eritas.agent_money VAAT — never written as x402 settle |
| **Plane visa** | eritas.agent_identity |
| **Product claim** | Still one flywheel-claim |

## Paths

| Artifact | Path |
|----------|------|
| Charter | docs/program/ECOSYSTEM_ADVANCE.md |
| Bus | docs/program/ecosystem/BUS.md |
| Conferral | docs/program/ecosystem/OVERSEER_CONFERRAL.md |
| Plane money | eritas/agent_money.py |
| Plane visa | eritas/agent_identity.py |

`
PROPERTY: cooperative track plane advances ecosystem gaps without dual product NEXT or fake settlement
EVIDENCE LEVEL: L0 (direction) + L1 (plane money/visa tests)
NOT PROVEN: billion-dollar EV; product on-chain settle; G10–G12 closed
`
