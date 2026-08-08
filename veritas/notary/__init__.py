"""Evidence notary: observe-once records of what a URL served at time T.

Import from submodules only — do not bind submodule names on this package
object (that shadows ``veritas.notary.<submodule>`` and breaks imports /
monkeypatch targets)::

    from veritas.notary.observe import observe
    from veritas.notary.fetch import fetch

Surface map (one engine; research ``observe_urls`` routes through observe):

* N0 — fetch, extract, record, licence/robots, observe, POST /v1/notarize
* N1.1 — optional EIP-191 attestation (``sign``)
* N1.2 — free attestation verify
* N1.3 — portable EvidencePack (``pack``)
* N1.4 — operator-local Merkle evidence log (``log`` / ``merkle``)
* N1.5 — inclusion proof embedded on completed observe
* P7 — origin re-fetch verify (``refetch``)

Public transparency log and on-chain anchors remain unclaimed.
"""

__all__: list[str] = []
