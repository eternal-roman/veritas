"""Agent-native layer: zero-key retrieval, self-provisioning, local settlement,
calibration, JIT packets, and wallet commitments.

This subpackage adds agent-facing concerns on top of the core engine in
`veritas`. It never reimplements the research pipeline — there is exactly one
engine (`veritas.pipeline`), and the control plane here calls into it.
"""
