# Distributable Setup

## Package Contents (agent-consumable)

- Core research engine (`veritas/`)
- Zero-key retrieval (`veritas/autonomous/zero_key_retrieval.py`)
- Payment configuration + live/free switch (`veritas/payment_config.py`)
- Local facilitator simulator (`veritas/autonomous/local_facilitator.py`)
- Self-calibrator, custody, hashing, identity, trust
- FastAPI surface with discovery endpoints (`veritas/server.py`)
- Evaluation harness

## Minimum Agent-to-Agent Deployment

1. Clone or install the package.
2. (Optional) Set live payment env vars.
3. Run the API or import the pipeline.
4. Publish the public URL + `/.well-known/x402` so other agents can discover it.

## Payment System Between Agents

- **Seller agent / service**: runs Veritas with `VERITAS_PAY_TO` set to an address it controls.
- **Buyer agent**: discovers the endpoint, receives 402, pays via x402 using its own wallet, retries with payment proof.
- **Facilitator**: public (OpenFacilitator / CDP) or self-hosted; settles on-chain.

No human is required in the payment or research loop once the service is running and the receiving wallet is funded/controlled by the seller agent or its operator.
