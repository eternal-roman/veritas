"""Evidence notary: observe-once records of what a URL served at time T.

N0 ships fetch, extract, record, licence/robots policy, and observe compose.
Signing, Merkle log, and re-fetch verify are N1 — not claimed here.
"""

from .fetch import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_BODY_BYTES,
    USER_AGENT,
    FetchError,
    FetchResult,
    fetch,
)

__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_BODY_BYTES",
    "USER_AGENT",
    "FetchError",
    "FetchResult",
    "fetch",
]
