# G9 — Chain reconcile design

**Status:** design + implementation surface shipped (`veritas/chain_reconcile.py`,
`veritas-ops reconcile-chain`, Phase **0.1-R** orchestrator
`python -m veritas.money_loop`). **Gap G9 remains open** until reconciliation
runs **routinely in production** and the constitution witness is retired.
Self-dogfood testnet settlements on tip: see `docs/program/fable/settlement/`.
Mainnet **0**. Unsolicited **0**.

## Problem

The ledger records what the **facilitator** told us (`settled` /
`indeterminate` / `failed`), including a `transaction_hash` when provided.
Nothing re-checks that hash against an RPC endpoint unless an operator (or
agent) runs reconcile. An operator can say what this instance *believes* it
earned, not what the chain *holds*.

Constitution article A13 / gap **G9**. Witness:
`tests/test_known_gaps.py::test_known_gap_settlements_are_never_checked_against_the_chain`
(pins: no `Ledger.reconcile_against_chain`, no `eth_getTransactionReceipt` in
`ledger.py`).

## Design principles

1. **RPC resolution (post-#119).** `resolve_rpc_url`: **env wins** for every
   network. If `VERITAS_RPC_URL` is unset, a **pinned public testnet** default
   applies only to networks in `DEFAULT_PUBLIC_RPC_URLS` (today
   `eip155:84532` → `https://sepolia.base.org`). **Mainnet never defaults** —
   a real mainnet tx checked against the wrong chain would read `not_found`.
   Unset env **downgrades coverage**, never correctness.
2. **Do not rewrite the money path.** Reconcile is a **report**, not a ledger
   mutation. Revenue stays facilitator-recorded until an operator acts.
3. **One RPC method for N1.** `eth_getTransactionReceipt` for exact-scheme
   USDC transfers we already stored a hash for. No multi-chain indexer in this
   slice.
4. **Keep G9 on the ledger module.** Chain RPC lives in
   `veritas.chain_reconcile`, not on `Ledger`, so the witness stays honest until
   the gap is intentionally closed.
5. **Injectable transport.** Tests never open sockets; production uses a thin
   JSON-RPC POST with a **versioned User-Agent** (Cloudflare rejects default
   `Python-urllib`).
6. **Routine path (0.1-R).** `veritas.money_loop` composes settle →
   `reconcile_settlements_auto` with exit-honest codes; does not claim G9
   closed.

## Operator surface

```bash
# Local consistency only (unchanged)
veritas-ops reconcile

# G9 path — env optional on known testnets
# export VERITAS_RPC_URL=https://…   # required for mainnet
veritas-ops reconcile-chain

# Phase 0.1-R: one agent-clearable settle → reconcile cycle
# BUYER_PRIVATE_KEY=… VERITAS_BASE_URL=… VERITAS_RUNTIME_DIR=… \
python -m veritas.money_loop --out-dir money_loop_runs
# exit 0 = confirmed this run; 2 = honest incomplete; 1 = transport failure
```

JSON includes `rpc_configured`, `chain_checked`, per-tx `status`
(`confirmed` | `reverted` | `not_found` | `rpc_not_configured` | …),
per-row `rpc_source` (`env` | `default_public_rpc:<network>` | `unconfigured`),
and the standing limitation text.

## Acceptance for closing G9 later

Not claimed by 0.1-R. To retire the gap:

1. Production ops run reconcile routinely (not one-off dogfood).
2. CI or dogfood exercises a real receipt classification against a public
   testnet hash (or a recorded fixture of a real response) as the default path.
3. Constitution G9 status → closed with resolution pointer; delete witness.

## What this does not claim

* Mainnet settlement or mainnet default RPC
* Unsolicited third-party buyers
* Multi-instance shared reconcile
* Automatic clawback or re-settlement
* G9 closed / production-routine complete
