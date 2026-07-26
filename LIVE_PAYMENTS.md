# Live Payment Configuration

## Quick start (live mode)

```bash
export VERITAS_PAY_TO=0xYourRealReceivingWallet
export VERITAS_FACILITATOR=https://pay.openfacilitator.io
export VERITAS_REQUIRE_PAYMENT=true
export VERITAS_NETWORK=eip155:8453
export VERITAS_PRICE=$0.25

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Recommended public facilitators

| Facilitator | URL | Notes |
|-------------|-----|-------|
| OpenFacilitator (public) | `https://pay.openfacilitator.io` | Free public endpoint, good starting point |
| Coinbase CDP | `https://api.cdp.coinbase.com/platform/v2/x402` | Production-grade, free tier then low fee |
| Self-hosted | Your own OpenFacilitator / x402-sovereign instance | Full control |

## What happens

- When `VERITAS_REQUIRE_PAYMENT=true` **and** a real `VERITAS_PAY_TO` is set, the service enters **live** mode.
- The payment gate will return HTTP 402 with x402 payment requirements pointing at your wallet and the configured facilitator.
- After the client pays, the facilitator verifies and settles; funds go to `VERITAS_PAY_TO`.

## Free / simulated mode (default)

If the env vars above are not set, the service stays in free mode and uses the local facilitator simulator. No real money moves. This is the zero-human-config path for agents.

## Testnet recommendation

For initial testing use Base Sepolia:

```bash
export VERITAS_NETWORK=eip155:84532
export VERITAS_FACILITATOR=https://x402.org/facilitator   # or a testnet-capable public facilitator
```

Then switch to mainnet (`eip155:8453`) once settlement is confirmed.
