# Veritas — Agent-Native Mission Status

## Goal
Close every human-in-the-loop door so an agent can discover, pay, call, and verify research with zero prior human configuration.

## Completed Autonomy Components

| Component | Path | Capability |
|-----------|------|------------|
| Zero-key retrieval | `autonomous/zero_key_retrieval.py` | Wikipedia + DuckDuckGo, no API keys |
| Bootstrap | `autonomous/bootstrap.py` | Generates local identity & free-mode config |
| Local facilitator | `autonomous/local_facilitator.py` | Records attempts & settlements without human wallet |
| Self-calibrator | `autonomous/self_calibrator.py` | Online frequency calibration from outcomes |
| Control plane | `autonomous/control_plane.py` | Single `agent_research()` entry, `human_required: false` |
| Core engine | `veritas/` | Custody, hashing, Bayesian, refusal |

## Agent usage (zero human setup)

```python
from autonomous.control_plane import agent_start, agent_research

agent_start()
result = agent_research("What is x402?")
assert result["human_required"] is False
```

## Still open (next rounds)
1. Real agent wallet (session keys / AgentKit) so the instance can receive live x402 without a human-exported key
2. Persistent public hosting that an agent can keep alive or re-spawn
3. Automatic IPFS / wallet-owned evidence pinning
4. Fully self-supervised calibration from real usefulness signals
5. On-chain ERC-8004 registration from the autonomous identity

The free research path and local payment simulation no longer require humans. Live economic autonomy is the next frontier.
