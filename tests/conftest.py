"""Test-session isolation for Veritas.

`veritas/server.py` builds its CustodyStore, OutcomeLog and Ledger at import
time, and each reads ``VERITAS_RUNTIME_DIR`` with a cwd-relative default of
``.veritas_runtime`` (open defect O5). Test modules import the server at
collection time, before any fixture can run, so without this file the whole
session shares one runtime directory in the repository root — and the suite
becomes order-dependent, which is what it was: 2 failed and 4 errors on a full
run against 4c3b23c, all six passing in isolation.

The environment variable is therefore bound at *conftest import* time. pytest
imports conftest before collecting test modules, so this is the only hook that
runs early enough to reach an import-time singleton.

This does not fix O5. `server.py` still binds at import and still defaults to
a relative path, and the 23 ``importlib.reload`` calls that work around it are
untouched. What it fixes is the suite's reproducibility, which every L1
enforcement pointer in the constitution ultimately cashes out to.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

# Bound before collection. setdefault, not assignment: an operator or CI job
# that pins VERITAS_RUNTIME_DIR deliberately keeps their value.
_SESSION_RUNTIME = Path(tempfile.mkdtemp(prefix="veritas-test-runtime-"))
os.environ.setdefault("VERITAS_RUNTIME_DIR", str(_SESSION_RUNTIME))


@pytest.fixture(autouse=True)
def isolated_runtime_dir(tmp_path, monkeypatch):
    """Give each test its own runtime directory.

    The session-level binding above stops state reaching the repository root.
    This stops it reaching the *next test*: any test that reloads
    `veritas.server` rebinds the singletons, and it should rebind them
    somewhere private rather than into a directory a sibling test also uses.
    """
    runtime = tmp_path / "runtime"
    runtime.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("VERITAS_RUNTIME_DIR", str(runtime))
    return runtime
