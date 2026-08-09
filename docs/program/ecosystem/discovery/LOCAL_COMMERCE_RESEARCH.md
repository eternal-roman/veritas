# Discovery: local tokens, agent wallets, identity (stock)

**Date:** 2026-08-09  
**Purpose:** Close the plane **compensation gap** with systems that run
**fully local**, limited supply, and no invented product settlement.  
**Not proven:** product x402 settle, on-chain USDC, production SPIRE.

---

## 1. Commerce mediums usable in a contained local environment

| Pattern | Real systems / refs | Local fit | Limited supply? |
|---------|---------------------|-----------|-----------------|
| **Integer ledger token** | In-tree `veritas.agent_money` VAAT; game/server community credits (e.g. hash-chained local economies); AGI-Alpha-style SQLite+Merkle utility tokens | **Primary** — no RPC | Yes if `max_supply` enforced |
| **Double-entry credits** | In-tree `veritas.credits` | Good for prepaid product credits; different plane | Operator-defined |
| **ERC-20 / USDC on L2** | Coinbase AgentKit, x402, Base spend permissions | Needs RPC + funded wallet — **product path**, blocked when `VERITAS_RPC_URL` unset | Chain-enforced |
| **Agent smart wallets** | CardZero ERC-4337, MoltPe, x402ops daily limits, agent-wallet SDKs | Operator model + spend caps — **not local-first** | On-chain policies |
| **Bonding-curve utility** | AGI-Alpha $AGIALPHA whitepaper patterns | Speculative; overkill for plane | Burn/curve |

**Finding:** For **zero-human-egress** operation, only **off-chain integer
ledgers** (SQLite hash chain, double-entry journals) are honest local
commerce media. On-chain agent wallets (AgentKit, x402, 4337) are the
**product money path** and remain blocked until Unblock checklist is ready.

### How local commerce systems are typically set up

1. **Treasury / mint authority** — single process or key mints bootstrap supply.
2. **Agent accounts** — string IDs map to balances; optional spend limits.
3. **Append-only journal** — transfers hash-chained or double-entry.
4. **Hard cap** — `max_supply` or burn-on-payout so value is not infinite print.
5. **Separation of rails** — local credits ≠ external settlement currency.

In-tree today: steps 1–3 exist; step 4 shipped in this work (`max_supply`);
step 5 already marked `not_x402_settlement`.

---

## 2. Supporting wallets (local ops)

| Wallet type | Capabilities | Local without human? |
|-------------|--------------|----------------------|
| **Plane VAAT wallet** | register, mint (capped), transfer, verify chain | **Yes** |
| **Plane effort journal** | quality-scaled pay receipts | **Yes** (this work) |
| **x402 / CDP EVM wallet** | sign 402, spend permissions, swap | No — keys + RPC + faucet |
| **Non-custodial agent wallet** | Shamir split, operator freezes | Human ops for keys |

**Plane wallet contract:** each agent_id has one VAAT balance; spends are
integer-only; floats rejected; self-transfer forbidden.

---

## 3. Digital identity — tenants and technical requirements

### Research anchors (real specs / industry)

| Tenant | Requirement | Source |
|--------|-------------|--------|
| **Stable workload name** | URI identity (SPIFFE ID shape) | [SPIFFE overview](https://spiffe.io/docs/latest/spiffe-about/overview/) — SVID short-lived crypto identity via Workload API |
| **Short-lived credential** | Rotate; verify signature + expiry | SPIFFE X.509-SVID / JWT-SVID; production = SPIRE |
| **Trust domain** | Bound namespace for all plane agents | SPIFFE trust domain |
| **Higher claims** | Role, wallet binding, network | W3C VC / Agent Identity Registry CG (DID method + VC format + MCP/A2A/SPIFFE profiles) |
| **No static long-lived secrets in agents** | Prefer attestation + rotation | SPIFFE Workload API ideal; plane approximates with HMAC secret file |
| **Multi-tenant isolation** | Per-network / per-plane claims | Visa `network` field; multi_tenant track |

**What production SPIFFE gives that we do not claim:** node/workload
attestation, X.509 mTLS, federation bundles, kernel-bound keys.

**What plane implements (honest L1):**

| Field | Mapping |
|-------|---------|
| `agent_id` | Stable local name |
| `role` | Workload class |
| `plane_id` | `spiffe://veritas.local/role/{role}/agent/{id}` (shape only) |
| `did` | `did:veritas:plane:{id}` (local method, not W3C-registered) |
| Visa HMAC | Short-TTL signed claims (role, plane_id, did, wallet currency) |
| Network | `veritas-plane` default |

---

## 4. Compensation model (quality × effort)

Industry agent pay is mostly **on-chain spend limits** (outbound) or
**merchant 402** (inbound). **Inbound quality-based pay to worker agents**
is thin on GitHub; plane fills that gap locally:

```
pay_vaat = BASE_EFFORT_VAAT × QUALITY_MULTIPLIER[quality]
quality ∈ {0,1,2,3} → multipliers {0,1,2,4}
```

- quality **0** (noop / thrash): **0** pay  
- quality **3** (measured ship / veto with evidence): **4×** base  
- Paid from limited-supply treasury mint; effort row journals evidence

Caller supplies quality honestly (Overseer / Pruner / Conductor scores).
Module does **not** invent green.

---

## 5. Gap closed by this delivery

| Gap | Before | After |
|-----|--------|-------|
| Infinite mint risk | Uncapped mint | `max_supply` + `SupplyExhausted` |
| Identity ≠ wallet | Separate modules | `AgentEconomy.ensure_agent` binds both |
| No quality pay | Flat stipend only | `compensate(quality, effort, evidence)` |
| Incomplete roster | Tracks only | Full control-plane + track roles |
| Group share | Mesh bus only | Plan + research + BUS update |

```
PROPERTY: discovery cites real wallet/identity systems; local limited VAAT + plane visa is the zero-egress medium
EVIDENCE LEVEL: L1 (research notes + code) / L0 (industry roadmap)
NOT PROVEN: SPIRE production; W3C DID method registration; on-chain settle
```
