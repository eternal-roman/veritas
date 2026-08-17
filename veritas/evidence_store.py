"""Content-addressed excerpt store, keyed by the published ``content_hash``.

Receipts hold hashes, not bodies (STATUS: "Durable evidence re-fetch").
This store is the missing half: the excerpt that hashed to ``sha256:…``
stays retrievable for the retention window, including after the origin
URL 404s.

Default location is ``$VERITAS_RUNTIME_DIR/evidence/``. When
``VERITAS_DATABASE_URL`` is set the same rows live in the shared store
so two instances behind a balancer return the same body.

Lookup of an unknown hash is a miss, not an error. Writes never raise
into the research path: a full disk must not fail a paid request.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .hashing import compute_content_hash, verify_content_hash
from .store import StoreUnavailable, connect_target, parse_database_url

_DEFAULT_RUNTIME_DIR = ".veritas_runtime"
_DIRNAME = "evidence"

#: Only a published hash may name a file. Same allowlist idea as custody
#: request ids: the value arrives on the wire in ``GET /v1/evidence/{hash}``.
SAFE_CONTENT_HASH = re.compile(r"\Asha256:[0-9a-f]{64}\Z")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS evidence_blobs (
    content_hash TEXT PRIMARY KEY,
    excerpt      TEXT NOT NULL,
    url          TEXT,
    title        TEXT,
    stored_at    TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def is_safe_content_hash(value: object) -> bool:
    return isinstance(value, str) and bool(SAFE_CONTENT_HASH.fullmatch(value))


class EvidenceStore:
    """Put / get excerpts by the hash the pipeline published."""

    def __init__(self, base_dir: str | Path | None = None) -> None:
        runtime = Path(
            base_dir
            or os.getenv("VERITAS_RUNTIME_DIR")
            or _DEFAULT_RUNTIME_DIR
        )
        self.base_dir = runtime / _DIRNAME

    def _file_path(self, content_hash: str) -> Path | None:
        if not is_safe_content_hash(content_hash):
            return None
        digest = content_hash.split(":", 1)[1]
        return self.base_dir / f"{digest}.json"

    def put(
        self,
        content_hash: str,
        excerpt: str,
        *,
        url: str | None = None,
        title: str | None = None,
    ) -> bool:
        """Persist one excerpt. Returns False on any refusal or I/O failure.

        Refuses when the hash does not match the excerpt: storing a body
        under the wrong digest would make ``GET /v1/evidence/{hash}`` a lie.
        """
        if not is_safe_content_hash(content_hash):
            return False
        ok, _ = verify_content_hash(excerpt, content_hash)
        if not ok:
            return False
        record = {
            "content_hash": content_hash,
            "excerpt": excerpt,
            "url": url,
            "title": title,
            "stored_at": _now(),
        }
        stored = False
        target = None
        try:
            target = parse_database_url()
        except StoreUnavailable:
            target = None
        if target is not None:
            stored = self._put_shared(target, record) or stored
        stored = self._put_file(record) or stored
        return stored

    def put_many(self, evidence: list[dict[str, Any]]) -> int:
        """Persist every well-formed evidence item. Returns the write count."""
        written = 0
        for item in evidence:
            digest = item.get("content_hash")
            excerpt = item.get("excerpt")
            if not isinstance(digest, str) or not isinstance(excerpt, str):
                continue
            if self.put(
                digest, excerpt,
                url=item.get("url") if isinstance(item.get("url"), str) else None,
                title=item.get("title") if isinstance(item.get("title"), str) else None,
            ):
                written += 1
        return written

    def get(self, content_hash: str) -> dict[str, Any] | None:
        """Return the stored record, or None if unknown / unsafe / corrupt."""
        if not is_safe_content_hash(content_hash):
            return None
        target = None
        try:
            target = parse_database_url()
        except StoreUnavailable:
            target = None
        if target is not None:
            found = self._get_shared(target, content_hash)
            if found is not None:
                return found
        return self._get_file(content_hash)

    def _put_file(self, record: dict[str, Any]) -> bool:
        path = self._file_path(record["content_hash"])
        if path is None:
            return False
        try:
            self.base_dir.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(f".{path.name}.tmp")
            try:
                tmp.write_text(json.dumps(record, separators=(",", ":")), encoding="utf-8")
                os.replace(tmp, path)
            except OSError:
                tmp.unlink(missing_ok=True)
                return False
        except OSError:
            return False
        return True

    def _get_file(self, content_hash: str) -> dict[str, Any] | None:
        path = self._file_path(content_hash)
        if path is None or not path.is_file():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(record, dict) or record.get("content_hash") != content_hash:
            return None
        return record

    def _put_shared(self, target: Any, record: dict[str, Any]) -> bool:
        try:
            conn = connect_target(target)
        except StoreUnavailable:
            return False
        try:
            conn.executescript(_SCHEMA)
            conn.execute(
                "INSERT INTO evidence_blobs "
                "(content_hash, excerpt, url, title, stored_at) VALUES (?,?,?,?,?)"
                " ON CONFLICT(content_hash) DO UPDATE SET"
                " excerpt=excluded.excerpt, url=excluded.url,"
                " title=excluded.title, stored_at=excluded.stored_at",
                (
                    record["content_hash"], record["excerpt"],
                    record.get("url"), record.get("title"), record["stored_at"],
                ),
            )
        except Exception:
            return False
        finally:
            conn.close()
        return True

    def _get_shared(self, target: Any, content_hash: str) -> dict[str, Any] | None:
        try:
            conn = connect_target(target)
        except StoreUnavailable:
            return None
        try:
            conn.executescript(_SCHEMA)
            row = conn.execute(
                "SELECT content_hash, excerpt, url, title, stored_at "
                "FROM evidence_blobs WHERE content_hash = ?",
                (content_hash,),
            ).fetchone()
        except Exception:
            return None
        finally:
            conn.close()
        if row is None:
            return None
        return {
            "content_hash": row["content_hash"],
            "excerpt": row["excerpt"],
            "url": row["url"],
            "title": row["title"],
            "stored_at": row["stored_at"],
        }


def hash_excerpt(excerpt: str) -> str:
    """Public alias so callers do not have to import hashing themselves."""
    return compute_content_hash(excerpt)
