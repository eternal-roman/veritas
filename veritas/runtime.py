"""Resolve the durable runtime directory.

O5: every store used to default to the cwd-relative string
``.veritas_runtime``. ``veritas-ops`` from another directory then read an
empty ledger, and a process that could not mkdir the cwd 503'd on the
first paid request instead of at readiness.

Resolution order:

1. An explicit ``base_dir`` argument (tests, ops ``--runtime-dir``).
2. ``$VERITAS_RUNTIME_DIR`` if set.
3. ``$VERITAS_AGENT_HOME/runtime`` if the agent home is set.
4. A pre-existing ``./.veritas_runtime`` directory (legacy; bound
   absolute so a later ``chdir`` cannot split state).
5. ``$XDG_DATA_HOME/veritas/runtime`` or ``~/.local/share/veritas/runtime``.

Every branch returns an absolute path. Relative env values are resolved
against the current working directory *once per call* — operators should
set an absolute path; ``veritas-agent`` does that for them.
"""

from __future__ import annotations

import os
from pathlib import Path

ENV_RUNTIME = "VERITAS_RUNTIME_DIR"
ENV_AGENT_HOME = "VERITAS_AGENT_HOME"
LEGACY_RELATIVE = ".veritas_runtime"


def default_runtime_dir() -> Path:
    """Home-relative default. Never cwd-relative."""
    xdg = (os.environ.get("XDG_DATA_HOME") or "").strip()
    if xdg:
        return Path(xdg).expanduser() / "veritas" / "runtime"
    return Path.home() / ".local" / "share" / "veritas" / "runtime"


def resolve_runtime_dir(base_dir: str | Path | None = None) -> Path:
    """Absolute directory where ledger, receipts, and sibling state live."""
    if base_dir is not None:
        return Path(base_dir).expanduser().resolve()
    env = (os.getenv(ENV_RUNTIME) or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    home = (os.getenv(ENV_AGENT_HOME) or "").strip()
    if home:
        return (Path(home).expanduser() / "runtime").resolve()
    legacy = Path.cwd() / LEGACY_RELATIVE
    if legacy.is_dir():
        return legacy.resolve()
    return default_runtime_dir().resolve()


def bind_agent_runtime(base_dir: str | Path) -> Path:
    """Point this process at ``{base_dir}/runtime`` unless already pinned.

    ``veritas-agent up`` calls this before importing the server so the
    wallet home and the ledger are the same tree. Existing env wins
    (``setdefault``): an operator who set ``VERITAS_RUNTIME_DIR`` keeps it.
    """
    home = str(Path(base_dir).expanduser().resolve())
    os.environ.setdefault(ENV_AGENT_HOME, home)
    runtime = str(Path(home) / "runtime")
    os.environ.setdefault(ENV_RUNTIME, runtime)
    return resolve_runtime_dir()


def probe_runtime_dir(base_dir: str | Path | None = None) -> tuple[bool, str | None]:
    """Can this process create and write the runtime directory?

    ``/readyz`` uses this so a missing or unwritable dir is a readiness
    failure, not a later silent 503. The reason is a type name only —
    filesystem paths do not go on the wire.
    """
    runtime = resolve_runtime_dir(base_dir)
    probe = runtime / ".readyz"
    try:
        runtime.mkdir(parents=True, exist_ok=True)
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
    except OSError as exc:
        return False, f"runtime_dir_unwritable:{type(exc).__name__}"
    return True, None
