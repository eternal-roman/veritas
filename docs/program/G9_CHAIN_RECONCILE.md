# G9 — Chain reconcile design

**Status:** design + fail-closed surface shipped (`veritas/chain_reconcile.py`,
`veritas-ops reconcile-chain`). **Gap G9 remains open** until operators
configure RPC and production uses it. On-chain settlements proven in this
sandbox: **0**.

## Problem

The ledger records what the **facilitator** told us (`settled` /
`indeterminate` / `failed`), including a `transaction_hash` when provided.
Nothing re-checks that hash against an RPC endpoint. An operator can say what
this instance *believes* it earned, not what the chain *holds*.

Constitution article A13 / gap **G9**. Witness:
`tests/test_known_gaps.py::test_known_gap_settlements_are_never_checked_against_the_chain`
(pins: no `Ledger.reconcile_against_chain`, no `eth_getTransactionReceipt` in
`ledger.py`).

## Design principles

1. **Fail-closed without config.** No `VERITAS_RPC_URL` →
   `status: rpc_not_configured`, `chain_checked: false`. Never invent
   confirmation.
2. **Do not rewrite the money path.** Reconcile is a **report**, not a ledger
   mutation. Revenue stays facilitator-recorded until an operator acts.
3. **One RPC method for N1.** `eth_getTransactionReceipt` for exact-scheme
   USDC transfers we already stored a hash for. No multi-chain indexer in this
   slice.
4. **Keep G9 on the ledger module.** Chain RPC lives in
   `veritas.chain_reconcile`, not on `Ledger`, so the witness stays honest until
   the gap is intentionally closed.
5. **Injectable transport.** Tests never open sockets; production uses a thin
   JSON-RPC POST when configured.

## Operator surface

```bash
# Local consistency only (unchanged)
veritas-ops reconcile

# G9 design path
export VERITAS_RPC_URL=https://…   # optional; omit → rpc_not_configured
veritas-ops reconcile-chain
```

JSON includes `rpc_configured`, `chain_checked`, per-tx `status`
(`confirmed` | `reverted` | `not_found` | `rpc_not_configured` | …), and the
standing limitation text.

## Acceptance for closing G9 later

Not claimed by this design PR. To retire the gap:

1. Operator-configured RPC is the default path for production ops docs.
2. CI or dogfood exercises a real receipt classification against a public
   testnet hash (or a recorded fixture of a real response).
3. Constitution G9 status → closed with resolution pointer; delete witness.

## What this does not claim

* Any on-chain settlement in this repository
* Multi-instance shared reconcile
* Facilitator `/supported` preflight (X1/X3)
* Automatic clawback or re-settlement
