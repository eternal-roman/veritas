# Veritas Status — Agent-Native R&D Mission

## Mission Goal
Eliminate every human-in-the-loop mandate so agents can discover, pay, and use high-assurance research with zero prior human configuration of the instance.

## Autonomy Progress

| Obstacle | Status | Solution Path |
|----------|--------|---------------|
| Search API keys | **Unblocked (free path)** | `autonomous/zero_key_retrieval.py` — DuckDuckGo + Wikipedia, no keys required |
| Payment receiving | Partially unblocked | Bootstrap generates free-mode config; public facilitators available; self-host options documented |
| Hosting / uptime | Documented | Agent-deployable package + free facilitator endpoints |
| Calibration | Structural | Harness + calibrator ready for self-supervised loops |
| Discovery | Present | .well-known, identity, MCP-ready surface |

## How an agent starts with zero human config

```bash
python -m autonomous.bootstrap
# Then run the service in free mode
VERITAS_MODE=free uvicorn app.main:app
```

The service will use only zero-key retrieval and can accept payments via public facilitators once a receiving address is set by the agent itself.

## Remaining hard problems
- Fully autonomous long-term hosting without any operator
- Agent-controlled key management for receiving wallets at scale
- High-quality free retrieval volume/rate limits

These are being attacked as stepwise agentic components in the `autonomous/` folder.
