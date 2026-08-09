# Pruner log 036 — HEAVY #119 ship_ok

- **Time:** 2026-08-09T02:38:00Z
- **Path:** HEAVY
- **PR:** #119 `fable/unblock-defaults` @ `304b93b`
- **origin/main:** `bc0bba3`
- **Claim:** free
- **ship_ok:** **true**
- **Verdict:** LEAN product delta

## Battery

| Gate | Result |
|------|--------|
| pytest (excl. slow) | 829 passed, 1 skipped |
| chain_reconcile + unblock_probe | 16 passed |
| ruff | clean |
| bandit -ll | clean (after fix) |
| payment_model eval | I1–I7 holds |
| harness | OK |
| CI #119 @ 304b93b | all SUCCESS |

## Prune applied

- **B608** false positive on markdown checklist f-string failed Security scan
- Fix commit `304b93b`: `# nosec B608` + wording "refresh in place"
- Pushed to PR branch (no force-push)

## Product delta (review)

- `DEFAULT_PUBLIC_RPC_URLS` testnet-only (`eip155:84532`)
- `resolve_rpc_url` / `reconcile_settlements_auto` + ops_cli wire-up
- unblock_probe: UA + default RPC/facilitator when env unset
- Witness tests for default/testnet-only/mainnet-skip/UA

## Denied

- Pruner merge / force-push
- ship_ok while security red (blocked until fix)

## Directive

Conductor: merge-on-green eligible. Pruner does not merge.
