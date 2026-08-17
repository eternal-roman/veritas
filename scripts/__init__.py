"""Operator and dogfooding scripts.

A package so CI and operators can run `python -m scripts.dogfood_cycleN`.
It is deliberately excluded from the wheel (`pyproject.toml` includes
`veritas*` only), and `tests/test_packaging.py` asserts the wheel ships
exactly one top-level package.
"""
