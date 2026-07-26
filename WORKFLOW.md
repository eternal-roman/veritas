# Veritas Agent-to-Agent Workflow

Complete path for one agent to obtain high-assurance research from another agent/service with payment.

## End-to-End Sequence

1. **Discovery**
   - Agent finds Veritas via:
     - Bazaar / x402 registry
     - MCP tool listing
     - `/.well-known/x402`
     - ERC-8004 identity (when registered)
     - Direct endpoint knowledge

2. **Capability Inspection**
   - `GET /v1/identity`
   - `GET /v1/trust`
   - `GET /v1/payment-config`
   - `GET /.well-known/x402`

3. **Payment Challenge**
   - Agent calls `POST /v1/research`
   - If live mode: receives HTTP 402 with `payTo`, `network`, `price`, `facilitator`

4. **Payment**
   - Agent signs x402 payment (EIP-3009 / exact scheme) from its own wallet
   - Submits payment proof via facilitator or payment header

5. **Settlement**
   - Facilitator verifies and settles on-chain
   - Funds arrive at `VERITAS_PAY_TO`

6. **Research Execution**
   - Veritas runs zero-key (or paid) retrieval
   - Builds evidence with content hashes
   - Applies Bayesian updates + custody ledger
   - Returns claims + evidence package

7. **Independent Verification**
   - Calling agent re-computes content hashes
   - Verifies custody chain
   - Optionally re-fetches evidence (local CAS or IPFS)

8. **Optional Calibration Feedback**
   - Self-calibrator can record outcome signals for future posteriors

## Free Mode vs Live Mode

| Step | Free Mode | Live Mode |
|------|-----------|-----------|
| Discovery | Same | Same |
| Payment | Simulated / skipped | Real x402 via facilitator |
| Settlement | Local recorder | On-chain to pay_to |
| Research | Zero-key retrieval | Same (or upgraded sources) |
| Verification | Full custody + hashes | Full custody + hashes |

## Distributable Unit

The repository itself is the distributable unit. An operator or agent can:

```bash
git clone https://github.com/eternal-roman/veritas.git
cd veritas
pip install -r requirements.txt
# Optional live config
export VERITAS_PAY_TO=0x...
export VERITAS_REQUIRE_PAYMENT=true
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or call the library directly:

```python
from veritas.pipeline import run_research
print(run_research("What is x402?"))
```
