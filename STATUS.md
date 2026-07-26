# Veritas Status — Live Payment Configuration

## Payment Modes

| Mode | How to activate | Real money? |
|------|-----------------|-------------|
| **Free / simulated** (default) | No special env vars | No |
| **Live** | Set `VERITAS_PAY_TO` + `VERITAS_REQUIRE_PAYMENT=true` | Yes |

## Live configuration (copy-paste)

```bash
export VERITAS_PAY_TO=0xYourRealReceivingWallet
export VERITAS_FACILITATOR=https://pay.openfacilitator.io
export VERITAS_REQUIRE_PAYMENT=true
export VERITAS_NETWORK=eip155:8453
export VERITAS_PRICE=$0.25

uvicorn app.main:app --host 0.0.0.0 --port 8000
```

See `LIVE_PAYMENTS.md` for full details and alternative facilitators (CDP, self-hosted).

## Agent-native free path remains available

When the live env vars are absent, the service continues to operate with zero-key retrieval and local settlement simulation (`human_required: false`).
