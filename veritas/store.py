"""Shared durable-store resolution for ledger, credits, and rate limits.

Ledger and credits default to per-instance SQLite files under
``VERITAS_RUNTIME_DIR``. Set ``VERITAS_DATABASE_URL`` to share one store
across processes on the same host (a sqlite file URL) or across hosts
(a postgres URL). Unset keeps the historical per-directory files.

This is the roadmap 6.2 seam. It does not invent a hosted database, and
it does not require Postgres for same-host multi-process. Multi-host HA
is the operator's Postgres; this module only honours the URL.

Accepted URLs:

* ``sqlite:///relative/path.sqlite3`` — cwd-relative file
* ``sqlite:////absolute/path.sqlite3`` — absolute file
* ``postgres://…`` / ``postgresql://…`` — requires the ``postgres`` extra

``:memory:`` is refused: financial state that dies with the process is
the defect this module exists to close.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATABASE_URL_ENV = "VERITAS_DATABASE_URL"

_SQLITE_PREFIX = "sqlite:"
_POSTGRES_PREFIXES = ("postgres://", "postgresql://")


class StoreUnavailable(RuntimeError):
    """The configured store could not be opened. Callers fail closed."""


@dataclass(frozen=True)
class DatabaseTarget:
    """Resolved destination for shared durable state."""

    kind: str  # "sqlite" | "postgres"
    path: Path | None = None
    dsn: str | None = None

    @property
    def shared(self) -> bool:
        return True


def database_url_from_env() -> str | None:
    raw = (os.getenv(DATABASE_URL_ENV) or "").strip()
    return raw or None


def parse_database_url(url: str | None = None) -> DatabaseTarget | None:
    """Parse a database URL. ``None`` / empty means per-instance default files."""
    raw = database_url_from_env() if url is None else url
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    if text.startswith(_SQLITE_PREFIX):
        return _parse_sqlite_url(text)
    lowered = text.lower()
    if lowered.startswith(_POSTGRES_PREFIXES):
        return DatabaseTarget(kind="postgres", dsn=text)
    raise StoreUnavailable(f"unsupported {DATABASE_URL_ENV} scheme")


def _parse_sqlite_url(url: str) -> DatabaseTarget:
    # Four slashes: sqlite:////abs/path → /abs/path
    # Three slashes: sqlite:///rel/path → rel/path
    rest = url[len(_SQLITE_PREFIX):]
    if rest.startswith("////"):
        path_text = rest[3:]  # keep the leading /
    elif rest.startswith("///"):
        path_text = rest[3:]
    else:
        # sqlite://hostname/path is not a local file we honour.
        raise StoreUnavailable("sqlite URL must be a local file path")
    if not path_text or path_text in {":memory:", "/:memory:"}:
        raise StoreUnavailable("refusing in-memory sqlite for financial state")
    # urlsplit on sqlite:////tmp/x yields path '//tmp/x'; normalise.
    if path_text.startswith("//"):
        path_text = path_text[1:]
    path = Path(path_text)
    if not path.is_absolute() and url.startswith("sqlite:////"):
        path = Path("/") / path
    return DatabaseTarget(kind="sqlite", path=path)


def resolve_database_url(url: str | None = None) -> DatabaseTarget | None:
    """Resolve the configured shared store, or None for per-instance files."""
    try:
        return parse_database_url(url)
    except StoreUnavailable:
        raise


class StoreConnection:
    """Minimal DB-API wrapper. Translates sqlite-flavored SQL for postgres.

    Handlers run in a threadpool; connections are not shared across threads.
    Autocommit is on; callers that need a write lock issue ``BEGIN IMMEDIATE``.
    """

    def __init__(self, target: DatabaseTarget) -> None:
        self.target = target
        self.kind = target.kind
        self._conn: Any
        if target.kind == "sqlite":
            if target.path is None:
                raise StoreUnavailable("sqlite target missing path")
            target.path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(target.path), timeout=10, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=FULL")
            self._conn = conn
        elif target.kind == "postgres":
            self._conn = _connect_postgres(target.dsn or "")
        else:
            raise StoreUnavailable(f"unknown store kind {target.kind!r}")

    def execute(self, sql: str, params: tuple[Any, ...] | list[Any] = ()) -> Any:
        translated = _translate_sql(sql, self.kind)
        if translated is None:
            return _NoopCursor()
        return self._conn.execute(translated, tuple(params))

    def executescript(self, script: str) -> None:
        if self.kind == "sqlite":
            self._conn.executescript(script)
            return
        for statement in _split_statements(script):
            translated = _translate_sql(statement, self.kind)
            if translated is None:
                continue
            self._conn.execute(translated)

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> StoreConnection:
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if exc_type is None:
                try:
                    self._conn.execute("COMMIT")
                except Exception:
                    pass
            else:
                try:
                    self._conn.execute("ROLLBACK")
                except Exception:
                    pass
        finally:
            self.close()


class _NoopCursor:
    """PRAGMA / no-op statement on a backend that does not speak it."""

    lastrowid = None
    rowcount = 0

    def fetchone(self) -> None:
        return None

    def fetchall(self) -> list:
        return []


def _connect_postgres(dsn: str) -> Any:
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError as exc:
        raise StoreUnavailable(
            "psycopg is not installed; pip install veritas-research[postgres]"
        ) from exc
    try:
        return psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
    except Exception as exc:  # noqa: BLE001 - fail closed; category only
        raise StoreUnavailable(type(exc).__name__) from exc


def _translate_sql(sql: str, kind: str) -> str | None:
    text = sql.strip()
    if not text:
        return None
    if kind == "sqlite":
        return text
    upper = text.upper()
    if upper.startswith("PRAGMA "):
        return None
    if upper == "BEGIN IMMEDIATE":
        return "BEGIN"
    text = text.replace(
        "INTEGER PRIMARY KEY AUTOINCREMENT",
        "INTEGER GENERATED BY DEFAULT AS IDENTITY PRIMARY KEY",
    )
    # sqlite '?' placeholders → psycopg '%s'
    text = text.replace("?", "%s")
    return text


def _split_statements(script: str) -> Iterator[str]:
    for part in script.split(";"):
        statement = part.strip()
        if statement:
            yield statement


def connect_target(target: DatabaseTarget) -> StoreConnection:
    try:
        return StoreConnection(target)
    except StoreUnavailable:
        raise
    except (sqlite3.Error, OSError) as exc:
        raise StoreUnavailable(type(exc).__name__) from exc


def sqlite_file_url(path: Path | str) -> str:
    """Build a ``sqlite:`` URL for an absolute or relative file path."""
    resolved = Path(path)
    if resolved.is_absolute():
        return f"sqlite:///{resolved}"
    return f"sqlite:///{resolved.as_posix()}"


_RATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS rate_hits (
    caller  TEXT NOT NULL,
    hit_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS rate_hits_by_caller ON rate_hits(caller, hit_at);
"""


def shared_rate_limited(caller: str, *, limit: int, window_seconds: float, now: float) -> bool:
    """True when ``caller`` has already used ``limit`` hits in the window.

    Uses the shared store. Callers that have no DATABASE_URL should keep
    the in-process limiter — this function refuses (fail closed as
    "not limited") only if the store cannot be opened, so a missing
    shared table never becomes a free pass *and* never 503s every
    request. The in-process limiter remains the fallback.
    """
    try:
        target = parse_database_url()
    except StoreUnavailable:
        return False
    if target is None:
        return False
    cutoff = now - window_seconds
    try:
        conn = connect_target(target)
    except StoreUnavailable:
        return False
    try:
        conn.executescript(_RATE_SCHEMA)
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("DELETE FROM rate_hits WHERE hit_at < ?", (cutoff,))
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM rate_hits WHERE caller = ? AND hit_at >= ?",
            (caller, cutoff),
        ).fetchone()
        count = int(row["n"] if row is not None else 0)
        if count >= limit:
            conn.execute("COMMIT")
            return True
        conn.execute(
            "INSERT INTO rate_hits (caller, hit_at) VALUES (?, ?)",
            (caller, now),
        )
        conn.execute("COMMIT")
        return False
    except Exception:
        try:
            conn.execute("ROLLBACK")
        except Exception:
            pass
        return False
    finally:
        conn.close()

