"""Operator and dogfooding scripts.

A package only so `tests/test_dogfood.py` can import the cycles and run them
in CI — a dogfooding cycle that ran once by hand is an anecdote. It is
deliberately excluded from the wheel (`pyproject.toml` includes `veritas*`
only), and `tests/test_packaging.py` asserts the wheel ships exactly one
top-level package.
"""
