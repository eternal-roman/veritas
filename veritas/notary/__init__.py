"""Evidence notary: observe-once records of what a URL served at time T.

N0 ships fetch, extract, record, licence/robots policy, and observe compose.
N1.1 adds optional EIP-191 attestation of bound record fields when an
operator signing key is configured. Merkle log, anchors, and re-fetch
verify remain later N1 work — not claimed here.

Import observation from the submodule so package attributes never shadow
module paths used by pipeline, server, and tests::

    from veritas.notary.observe import observe
    from veritas.notary.fetch import fetch

Research routes URL observation through ``observe`` when
``observe_urls=True`` (one engine — never a second scraper).
"""

# Do not re-export symbols whose names match submodule names (fetch, observe,
# extract, record, license, robots). Binding those on the package object
# shadows `veritas.notary.<submodule>` attribute access and breaks
# `from veritas.notary.observe import observe` / monkeypatch targets.
from .fetch import (
    DEFAULT_TIMEOUT_SECONDS,
    MAX_BODY_BYTES,
    USER_AGENT,
    FetchError,
    FetchResult,
)

__all__ = [
    "DEFAULT_TIMEOUT_SECONDS",
    "MAX_BODY_BYTES",
    "USER_AGENT",
    "FetchError",
    "FetchResult",
]
