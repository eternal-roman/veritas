# Unblock CHECKLIST (living — update in place)

**Updated:** 2026-08-09T02:21Z by `python -m veritas.unblock_probe`
**Rule:** Do **not** open a docs PR just to rewrite this file unless a required
row flips with new evidence. Settlement count lives with its evidence
(`docs/program/fable/settlement/`), never restated here (MIND §5).

## Probes

| Item | Status | Evidence |
|------|--------|----------|
| VERITAS_RPC_URL | yes | eth_chainId=0x14a34 — via pinned public default https://sepolia.base.org (VERITAS_RPC_URL unset; setting it overrides) |
| facilitator | yes | HTTP 200 from https://x402.org/facilitator/supported — via pinned public default https://x402.org/facilitator (facilitator env unset; setting it overrides) |
| wallet_key_configured | no | VERITAS_BUYER_KEY unset |
| funded_testnet_wallet | unknown | balance not probed; funding is permissionless (faucet.circle.com) — see docs/program/fable/STATE.md walkthrough |
| test_usdc | unknown | balance not probed; permissionless faucet covers it |
| public_tls_host | optional | not probed; optional for 0.1 (Stage-1 human residue) |
| pypi_trusted_publisher | optional | human minutes: PyPI-side trusted-publisher config; agent-prepared 90%: .github/workflows/release.yml (tag-triggered) |

## Required for Phase 0.1 dogfood

- Chain RPC responds (env **or** pinned public testnet default — env unset is
  not a block, MIND §3)
- Facilitator reachable (env **or** pinned public default)
- Funded wallet + test USDC (permissionless faucet; balance unconfirmed until
  a run spends it)

**Required automated ready?** **yes** (RPC+facilitator)

## Next

If required automated ready → confer Overseer: singular product NEXT =
Phase 0.1 repeat / G9 routine reconcile (recipe: docs/program/fable/STATE.md).

```
PROPERTY: unblock checklist reflects live probes with sources labelled; no invented settle
EVIDENCE LEVEL: L1 (env/http probes) / L0 (funding balance)
NOT PROVEN: mainnet settlement; unsolicited buyers
```
