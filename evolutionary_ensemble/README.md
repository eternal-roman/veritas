# evolutionary_ensemble (directive scaffold)

This directory is the **assimilation map** for the Evolutionary Creativity
Algorithm directive. The installable implementation lives inside the single
Veritas package (wheel must remain one top-level package):

| Directive file | Veritas path |
|----------------|--------------|
| `state.py` | `veritas/evolver/state.py` |
| `prompts.py` | `veritas/evolver/prompts.py` |
| `agents.py` | `veritas/evolver/agents.py` |
| `graph.py` | `veritas/evolver/graph.py` |
| `main.py` | `python -m veritas.evolver` / `veritas-evolver` |

```bash
pip install -e ".[evolver]"   # optional LangGraph
python -m veritas.evolver "Your problem" --no-langgraph --print-bus
```

Program role: **Evolver** (formerly Scout Idea agent) — see
`docs/program/EVOLVER.md`. Outputs are WATCH fuel, never STATE NEXT.
