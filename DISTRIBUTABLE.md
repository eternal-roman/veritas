# Distributable Setup

## Package Contents (agent-consumable)

- Core research engine (`veritas/`)
- Zero-key retrieval (`veritas/autonomous/zero_key_retrieval.py`), keyed
  Serper tier (`veritas/providers.py`)
- Payment configuration + live/free switch (`veritas/payment_config.py`)
- Buyer payment path with spend caps (`veritas/payer.py`,
  `veritas/buyer_payment.py`)
- Seller-side financial ledger and replay state machine (`veritas/ledger.py`) —
  authorizations, deliveries and settlement attempts, on SQLite
- Wallet self-provisioning (`veritas/autonomous/wallet.py`) and the
  `veritas-agent` CLI (`veritas/agent_cli.py`)
- Local facilitator simulator (`veritas/autonomous/local_facilitator.py`) —
  structural checks only, see constitution gap G2
- Self-calibrator, custody, hashing, identity, trust, constitution
- FastAPI surface with self-traversing discovery (`veritas/server.py`),
  error registry (`veritas/errors.py`), `llms.txt` (`veritas/discovery.py`)
- MCP stdio tools (`veritas/mcp_server.py`, `veritas-mcp`)
- Evaluation harness

## Minimum Agent-to-Agent Deployment

```bash
pip install "veritas-research[signing] @ git+https://github.com/eternal-roman/veritas"
veritas-agent up            # config + wallet + serve, free mode
veritas-agent up --paid     # same, requiring payment to the agent's wallet
```

Or containerised: `docker build -t veritas-research . && docker run -p 8000:8000 veritas-research`.

What `up` provisions with no human input: the agent config, a locally minted
encrypted wallet keystore (its address becomes `pay_to`), and a running
server whose environment reflects that config. What remains external, stated
plainly: funding the wallet, TLS/public deployment, and publishing the URL
(registry announcement is ROADMAP Phase 4).

## Payment System Between Agents

- **Seller agent / service**: runs Veritas with `pay_to` set to an address it
  controls — `veritas-agent up --paid` uses the self-provisioned wallet.
- **Buyer agent**: discovers the endpoint, receives 402, pays via x402 within
  its spend policy (`veritas.buyer_payment.pay_via_policy`), retries with
  payment proof. Resubmitting an authorization never buys a second retrieval
  pass; if the work was already delivered it is returned again from the
  ledger, so a dropped connection does not cost the buyer their payment.
- **Facilitator**: public (OpenFacilitator / CDP) or self-hosted; settles
  on-chain. No settlement has yet been proven end-to-end (ROADMAP 0.1).

Once the service is running and the receiving wallet is funded, the payment
and research loop is agent-to-agent; the funding step and public deployment
are the remaining human touchpoints.
