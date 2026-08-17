# Autonomous helpers

First engagement is `veritas-agent adopt` (see root `AGENTS.md`), not these
files directly.

- `wallet.py` — local ETH keystore used as x402 `pay_to`. Funding is external.
- `zero_key_retrieval.py` — Wikipedia extracts + DDG Instant Answer. No API keys.
- `bootstrap.py` — free-mode config that `veritas-agent` applies to the served env.
- `local_facilitator.py` — signature check for free/local mode. G13 nonce/balance stay on-chain.
