# Autonomous helpers

First engagement is `veritas-agent adopt` (see root `AGENTS.md`), not these
files directly.

- `wallet.py` — local ETH keystore used as x402 `pay_to`. Funding is external.
- Catalog pull is `veritas.signals`, not these files.
- `bootstrap.py` — free-mode config that `veritas-agent` applies to the served env.
- `local_facilitator.py` — signature check for free/local mode. G13 nonce/balance stay on-chain.
