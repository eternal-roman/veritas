# Architect CURRENT

- **Time:** 2026-08-09T03:12:00Z
- **Tip:** `origin/main` @ **`c6dc73f`** (#121 claim building hygiene; product base **#119** `fb3b0d5`)
- **Claim:** **building** `phase-0.1-R` · holder flywheel · **origin claim file now matches** (post-#121)
- **Product branch:** `feat/phase-0.1-R-routine-money-loop` @ tip · **zero product code delta** · **no open PR**
- **Mode:** building + branch exists → reaffirm constraints; map re-materialized (prior uncommitted map was lost)
- **Open PRs:** **none**
- **Confer Scout?** no
- **Living map:** [`../ARCHITECTURE.md`](../ARCHITECTURE.md)

## builder_directive (Flywheel / Implement — singular)

**bet_id:** `phase-0.1-R`  
**base:** `c6dc73f` (includes claim truth) / product surface from `fb3b0d5`  
**branch:** **already created** `feat/phase-0.1-R-routine-money-loop` — continue here; do not open a second branch for the same bet

### Scope (one PR)

1. **Orchestrate** settle → chain reconcile into one agent-clearable path
   (prefer extend `scripts/testnet_settlement.py` or thin `veritas.money_loop`
   module) using **existing** `pay_via_policy` / `veritas.payer` and
   `reconcile_settlements_auto` (or CLI equivalent against the **same**
   runtime ledger as the live server).
2. **Evidence JSON** with: steps, acceptance.met, transaction, reconcile
   `chain_checked`, per-row `rpc_source`, `runtime_dir` / ledger identity,
   finished_at. Exit codes distinguish success / honest refusal /
   transport-or-config failure.
3. **Tests (offline):** pin testnet default resolution + `rpc_source`; pin
   mainnet absent from defaults; pin versioned User-Agent on RPC transport;
   orchestrator does not invent green on empty ledger / unconfigured mainnet.
4. **Honesty touch-ups in-scope:** align `G9_NOTE` / `G9_CHAIN_RECONCILE.md`
   with post-#119 defaults (testnet default OK; mainnet explicit; G9 still open).
5. **Docs minimal:** recipe pointer only if needed; PROPERTY: not mainnet /
   not unsolicited / G9 not closed. Absorb this ARCHITECTURE.md in the product PR.

### Non-goals

mainnet, PyPI, TLS, M7, N0, second payer/engine, dual continuous, close G9
witness, restock-only PR, reopen #112/#119 thrash, second product branch.

### Packages if Implement×n (n≤3, non-overlapping)

| id | files | done when |
|----|-------|-----------|
| P1 orchestrator | `scripts/testnet_settlement.py` and/or `veritas/money_loop.py` + pyproject entry if any | one command runs settle then reconcile; honest exits |
| P2 tests | `tests/test_money_loop.py` and/or extend `tests/test_chain_reconcile.py` | offline pins above green |
| P3 honesty docs | `veritas/chain_reconcile.py` note strings; `docs/program/G9_CHAIN_RECONCILE.md`; optional fable recipe one-liner | no claim G9 closed; defaults truth |

Integrator owns battery + PR description PROPERTY block. Pruner HEAVY before ship.

### First commands

```text
git fetch origin
git checkout feat/phase-0.1-R-routine-money-loop
git merge --ff-only origin/main   # stay at c6dc73f+
# implement P1–P3 on this branch only
python -m pytest tests/test_chain_reconcile.py tests/test_payment.py -q
python -m pytest tests/ -q
ruff check veritas tests scripts
bandit -r veritas scripts -ll -q
# then: open ONE product PR → CI → Pruner ship_ok → merge
```

Live dogfood (optional evidence, not CI gate): funded buyer + live-mode server
per `docs/program/fable/STATE.md`, then default-path reconcile with env unset.

## Attention

| Risk | Action |
|------|--------|
| Claim building + **no code + no PR** | Flywheel/Implement must land P1–P3 this cycle; Architect does not invent product code outside seam map |
| Dual branch | This branch is the G10 holder surface — do not open parallel 0.1-R branches |
| Card lag | Conductor/Overseer CURRENT may still say tip `fb3b0d5` — in-place restock only; no hygiene PR while product claim holds |

## PROPERTY

```
PROPERTY: tip c6dc73f; claim building phase-0.1-R; product branch exists zero-delta; open PRs none; architect map re-written; builder_directive = compose settle+reconcile only
EVIDENCE LEVEL: L1
CHECKED ARTIFACT: plane_stock; origin/main c6dc73f; branch feat/phase-0.1-R-routine-money-loop; open PR []; ARCHITECTURE.md
ASSUMPTIONS: flywheel continues on this branch; G10 singular
NOT PROVEN: 0.1-R code; product PR; production G9; mainnet; unsolicited
```
