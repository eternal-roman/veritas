# Autonomous Components for Veritas

Gap-filling, agent-native modules that remove human-in-the-loop requirements.

First engagement is `veritas-agent enroll` (see root `AGENTS.md`), not these
files directly.

## Components

- `wallet.py` — Local ETH keystore used as x402 `pay_to`. Funding is external.
- `zero_key_retrieval.py` — Free multi-source search (DuckDuckGo + Wikipedia). No API keys.
- `bootstrap.py` — Free-mode config that `veritas-agent` applies to the served env.
- JIT / hiding-wallet prototypes — experiments, not product surfaces (`docs/design/`).
