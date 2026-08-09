# Unblock CHECKLIST (living — update in place)

**Updated:** 2026-08-09T01:03Z by `python -m veritas.unblock_probe`
**Rule:** Do **not** open a docs PR just to rewrite this file unless a required
row flips with new evidence. Product settle remains **0** until 0.1 dogfood.

## Probes

| Item | Status | Evidence |
|------|--------|----------|
| VERITAS_RPC_URL | no | VERITAS_RPC_URL unset |
| facilitator | no | facilitator URL unset |
| wallet_key_configured | no | VERITAS_BUYER_KEY unset |
| funded_testnet_wallet | unknown | requires human confirmation of faucet balance |
| test_usdc | unknown | requires human confirmation of USDC balance |
| public_tls_host | optional | not probed; optional for 0.1 |
| pypi_trusted_publisher | optional | human ops; not required for 0.1 |

## Required for Phase 0.1 dogfood

- `VERITAS_RPC_URL` → **yes** and chain responds
- Facilitator URL reachable
- Funded wallet + test USDC (human)

**Required automated ready?** **no**

## Next

If required automated ready **and** human confirms funding → confer Overseer:
singular product NEXT = Phase 0.1 / G9 dogfood.

```
PROPERTY: unblock checklist reflects probes; no invent settle
EVIDENCE LEVEL: L1 (env/http probes) / L0 (funding)
NOT PROVEN: on-chain settlement success
```
