"""Cold archive of pruned custody receipts.

Retention already deletes aged receipt bodies and leaves a 410 tombstone.
Without an archive those bodies are gone. Set ``VERITAS_ARCHIVE_DIR`` and
``CustodyStore.prune`` copies each body here *before* deleting it.

This is a local directory, not IPFS and not S3. Those would need
credentials this repository does not invent (invariant 11). An operator
who wants object storage points the directory at a mounted bucket.

If the archive is configured and a write fails, prune skips that receipt
so the live copy is not the last copy we then delete.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from .custody import is_safe_request_id

ARCHIVE_DIR_ENV = "VERITAS_ARCHIVE_DIR"


def archive_dir() -> Path | None:
    raw = (os.getenv(ARCHIVE_DIR_ENV) or "").strip()
    if not raw:
        return None
    return Path(raw)


def archive_enabled() -> bool:
    return archive_dir() is not None


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except OSError:
        tmp.unlink(missing_ok=True)
        raise


def archive_receipt(record: dict[str, Any]) -> bool:
    """Write one receipt body into the archive. False if archive is unset.

    Raises OSError on a configured-but-unwritable archive so the caller
    can refuse to delete the live copy.
    """
    root = archive_dir()
    if root is None:
        return False
    request_id = record.get("request_id")
    if not is_safe_request_id(request_id):
        raise OSError("unsafe request_id")
    body = json.dumps(record, indent=2, sort_keys=True)
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    by_id = root / "receipts" / f"{request_id}.json"
    by_hash = root / "sha256" / f"{digest}.json"
    _atomic_write(by_id, body)
    _atomic_write(by_hash, body)
    return True
