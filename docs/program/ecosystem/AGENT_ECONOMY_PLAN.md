# Plan: local agent economy (identity · wallet · quality pay)

**Status:** implementable without human intervention (plane only).  
**Overseer class:** explicit **non-money product bet** alternative — plane
substrate, **not** Phase 0.1 / G9.  
**Honesty:** `not_x402_settlement` always.

---

## Objective

Every established plane agent has:

1. **Identity** — verifiable plane visa + SPIFFE-shaped id + local DID  
2. **Wallet** — limited-supply VAAT balance  
3. **Compensation** — VAAT for each effort, scaled by quality 0–3  

Close the **compensation gap** so agents are not “free thrash labor” in the
control plane, while product USDC remains 0 until Unblock completes.

---

## Autonomous build phases (no human gates)

### Phase A — Ledger hard cap (done this PR)

- [x] `max_supply` / `total_minted` / `remaining_supply` on `AgentMoneyLedger`
- [x] `SupplyExhausted` on over-mint
- [x] Snapshot reports limited supply

### Phase B — Economy binder (done this PR)

- [x] `veritas.agent_economy.AgentEconomy`
- [x] `ensure_agent` → register + visa + optional stipend
- [x] `compensate(quality, effort_kind, evidence)`
- [x] Effort SQLite journal
- [x] Full roster bootstrap (`python -m veritas.agent_economy`)
- [x] L1 tests

### Phase C — Wire roles (next continuous ticks — no PR spam)

Agents, on successful measured work, may call (local):

```bash
python -c "from veritas.agent_economy import AgentEconomy; e=AgentEconomy(); e.ensure_agent('steward','steward'); print(e.compensate('steward', 2, effort_kind='card_cohesion', evidence='noop_coherent tip true')); e.close()"
```

Or mesh LEARN every 5 cycles: pay top tracks from quality scores in
`ecosystem_cycle` (optional follow-up — do not dual product NEXT).

### Phase D — Multi-tenant plane (later)

- Separate `network` / ledger path per tenant
- Visa `network` already exists; ledger isolation is file-path based today

### Phase E — Product bridge (blocked on Unblock)

- Map plane identity → SIWx buyer when G9 dogfood ready  
- **Never** auto-convert VAAT → USDC without explicit operator policy

---

## Quality rubric (who may set quality)

| Score | Meaning | Example pay (base 25) |
|-------|---------|------------------------|
| 0 | noop / thrash / no evidence | 0 |
| 1 | honest stock + noop with PROPERTY | 25 |
| 2 | material fix / merge hygiene / probe flip | 50 |
| 3 | product ship_ok or measured unblock flip | 100 |

**Who sets score:** the agent’s gate (Overseer for strategy, Pruner for
ship_ok, self-report only if evidence path is cited — prefer peer gate).

---

## Operator zero-touch sequence

```bash
# 1. Bootstrap full plane (local)
python -m veritas.agent_economy

# 2. Optional: plane_bootstrap legacy roster
python -m veritas.plane_bootstrap

# 3. Mesh cycles still offline
python -m veritas.ecosystem_cycle --cycles 5

# 4. Unblock product money when ready
python -m veritas.unblock_probe
```

No GitHub, no RPC, no PyPI required for A–C.

---

## Group share (broader plane)

| Audience | Artifact |
|----------|----------|
| All agents | `ecosystem/BUS.md` message |
| Overseer | `ecosystem/OVERSEER_CONFERRAL.md` mark **accept plane economy** |
| Money track | `TRACK_MONEY_LOOP` — plane rail complete; product still G9 |
| Legal identity | Visa + DID/SPIFFE mapping in research doc |
| Hygiene | Still one hygiene PR/epoch; this is **plane code** singular bet |

---

## Acceptance (L1)

1. `pytest tests/test_agent_economy.py tests/test_agent_money.py -q` green  
2. Mint beyond `max_supply` raises `SupplyExhausted`  
3. Quality 0 pays 0; quality 3 pays 4× base  
4. Visa verifies after ensure_agent  
5. Snapshot has `not_x402_settlement: true` and `limited_supply: true`

```
PROPERTY: every roster agent can hold visa+VAAT; quality pay is deterministic and supply-capped
EVIDENCE LEVEL: L1
NOT PROVEN: fair human evaluation of quality; production SPIFFE; product settle
```
