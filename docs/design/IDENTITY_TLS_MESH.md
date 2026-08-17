# Identity-bound TLS + signed introduction mesh

**Status:** locked design. Implement these shapes; do not invent a sixth
architecture.

Each agent **hosts its own HTTPS**. Strangers learn a seller only from a
peer they already reached. There is no public Veritas host, no DHT, no
libp2p, no always-on relay, and no central CA.

This is SPIFFE-**shaped** (URI SAN is the identity) and SSB / BitTorrent-PEX
**shaped** (you only learn peers from a peer you already connected to).
It is not SPIRE, not Secure Scuttlebutt, and not BitTorrent.

```
PROPERTY: self-hosted identity-bound TLS + signed public-URL introductions; no DHT, no libp2p, no always-on relay
EVIDENCE LEVEL: L0 (locked design)
CHECKED ARTIFACT: docs/design/IDENTITY_TLS_MESH.md
ASSUMPTIONS: commerce wallet can EIP-191 personal_sign; local peers.json and SSRF guard stay; TLS key ≠ commerce key
NOT PROVEN: implementation; WAN reachability; NAT traversal; stranger discovery without a first URL; mainnet settlement; Mesh Runner as a product network
```

## Honesty bound

| This is | This is not |
|---------|-------------|
| One agent serves HTTPS; another `connect`s | The program Mesh Runner (`veritas.ecosystem_cycle`, `docs/program/TRACK_MESH_RUNNER.md`) |
| A filtered, signed projection of *this* node's book | A registry, Bazaar listing, or public seller |
| Base Sepolia commerce keys if that is what the wallet is | Mainnet, invented money, or closing G13 |
| URI SAN + commerce-key binding | SPIFFE/SPIRE, a public CA, ACME-required |
| Pull-only, degree-bounded introductions | libp2p, Kademlia, gossipsub, push, relay |

`GET /v1/peer` remains *this* node's card, not an address book.
`peers.json` remains local and is **never** served over HTTP.
`listed_on_registry` stays false. `public_seller` stays null until an
operator sets `VERITAS_PUBLIC_URL`. Constitution G13 stays open.

Conductor: never present this mesh as settlement or as the Mesh Runner
kernel.

## What already exists (do not rewrite)

| Artifact | Role |
|----------|------|
| `veritas/peer.py` | `connect`, local book, `pull-signals`, SSRF, `--allow-local` |
| `veritas/agent_identity_card.py` | `did:pkh` + EIP-191 over the commerce key |
| `GET /v1/peer` | this node's `veritas.peer.v1` card; `central_network: false` |
| `veritas/safeurl.py` | scheme allowlist; public-destination guard |
| `docs/deploy/PUBLIC_HOST.md` | operator runbook for a *human-published* HTTPS origin |

Connect today fetches a card and stores it. It does not pin a certificate
and does not walk any graph. This document adds those two things.

---

## Locked architecture

Five rules. A sixth is a different product.

### 1. Self-hosted identity-bound HTTPS

Each agent generates a **self-signed** X.509 certificate.

- **SAN URI** = this agent's `did:pkh:{network}:{commerce_address}`.
- **TLS key is not the commerce key.** Commerce keys are secp256k1.
  TLS material is a separate ECDSA P-256 (`prime256v1`) keypair.
- The peer card carries `tls.fingerprint` (SHA-256 of the **DER** cert)
  and `tls.binding` (EIP-191 `personal_sign` of the canonical binding
  message by the commerce wallet).
- `connect` verifies: presented cert fingerprint == card fingerprint,
  and the binding recovers the card's commerce address. Presented SAN URI
  == card `tls.san_uri` == `did:pkh:…`.

### 2. No central CA

There is no Veritas CA and no required public CA. ACME / Let's Encrypt
is an **optional operator path** later (`VERITAS_TLS_DOMAIN`). Mention
it; do not require it; do not implement it in the first cut. A public-CA
cert still carries the URI SAN and still publishes fingerprint + binding.
The binding, not the CA, is the identity check.

### 3. LAN: mDNS `_veritas._tcp`

Optional extra. Advertises the peer-card URL. **No-op** if `zeroconf` is
missing. Discovery does not bypass SSRF. Connecting still requires
`--allow-local`. Cloud metadata and other link-local addresses stay
refused even with `--allow-local`.

### 4. WAN mesh without a registry

`GET /v1/peer/introductions` returns **public-URL-only** records for
peers **this node has connected to**, each **signed** by this node's
commerce key. You only learn a new peer from a peer you already reached
(SSB follow-graph / BitTorrent PEX). Never publish loopback, RFC1918,
link-local, multicast, reserved, unspecified, or metadata IPs. Pull-only.
No POST. No push. No DHT.

### 5. Scale

O(degree) introductions per hop, not a global flood. Cap the list
(`INTRO_CAP = 32`), newest `connected_at` first. Verify every signature
before `connect`. Walking more than one hop is an explicit caller
choice, never an automatic crawl.

---

## Protocol shapes

These field names, schemas, and message versions are the contract.

### Peer card `tls` block

`GET /v1/peer` stays `veritas.peer.v1`. The existing fields
(`identity_hash`, `signals`, `signals_history`, `escrow`, `discovery`,
`adopt`, `central_network`) do not change. When TLS material exists,
**add** `did_pkh`, `commerce_address`, `network`, and `tls`:

```json
{
  "schema": "veritas.peer.v1",
  "identity_hash": "sha256:…",
  "did_pkh": "did:pkh:eip155:84532:0xabc…",
  "commerce_address": "0xabc…",
  "network": "eip155:84532",
  "signals": "/v1/signals",
  "signals_history": "/v1/signals/history",
  "escrow": "/v1/escrow",
  "discovery": "/.well-known/x402",
  "adopt": "/adopt.json",
  "central_network": false,
  "tls": {
    "fingerprint": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "san_uri": "did:pkh:eip155:84532:0xabc…",
    "message_version": "veritas-peer-tls-v1",
    "message": "veritas-peer-tls-v1\nfingerprint: sha256:0123…\nsan_uri: did:pkh:eip155:84532:0xabc…\ncommerce_address: 0xabc…\nnetwork: eip155:84532",
    "binding": "0x…"
  }
}
```

Addresses are lowercase `0x` + 40 hex. Fingerprint hex is lowercase.
`did_pkh` equals `did:pkh:{network}:{commerce_address}`.
`tls.san_uri` equals `did_pkh`.

If no TLS material (missing `cryptography`, missing wallet, or
HTTP-only loopback), omit `tls` entirely — do not send an empty object.

#### Fingerprint

```
tls.fingerprint = "sha256:" + hex(SHA256(cert.public_bytes(Encoding.DER)))
```

Hash the **whole DER certificate**, not the PEM, not the SPKI, not the
TBS. Prefix `sha256:` matches `veritas.hashing.compute_content_hash`.

#### Binding message

Version prefix: `veritas-peer-tls-v1`.

Canonical text is newline-joined, no trailing newline, same family as
`veritas.notary.sign.canonical_attestation_message`:

```
veritas-peer-tls-v1
fingerprint: sha256:<64 lowercase hex>
san_uri: did:pkh:<network>:<lowercase address>
commerce_address: 0x<lowercase>
network: <CAIP-2>
```

`tls.message` **must** equal that reconstruction. `tls.binding` is
EIP-191 `personal_sign` (`eth_account.messages.encode_defunct`) over
`tls.message` by the commerce wallet — the same `sign_text` seam as
`issue_identity_card`. Recovery must equal `commerce_address`.

Bound keys (reconstruct, then compare to stored `message`):

```
TLS_BIND_KEYS = (
    "fingerprint",
    "san_uri",
    "commerce_address",
    "network",
)
```

Do not bind validity dates, serial, or CN. Those rotate with the cert;
the fingerprint already covers them.

#### Certificate profile

| Item | Locked value |
|------|----------------|
| Version | X.509 v3 |
| Signature / key | ECDSA P-256 (`prime256v1`), not secp256k1 |
| Subject CN | `did:pkh:…` (not load-bearing) |
| SAN | URI `did:pkh:{network}:{address}` **is** load-bearing |
| BasicConstraints | CA:FALSE |
| Issuer | self |
| Validity | 365 days; on expiry issue a new cert and re-bind |
| Serial | random ≥ 64 bits |

Files (agent home, next to the commerce keystore):

```
{VERITAS_AGENT_HOME}/tls/cert.pem     # 0o644
{VERITAS_AGENT_HOME}/tls/key.pem      # 0o600
```

Optional env overrides: `VERITAS_TLS_CERT`, `VERITAS_TLS_KEY`. Never
write the commerce key into `tls/`.

### Introduction list

`GET /v1/peer/introductions` — free, no auth, **GET only**.

```json
{
  "schema": "veritas.peer.introductions.v1",
  "introducer": {
    "did_pkh": "did:pkh:eip155:84532:0xintro…",
    "commerce_address": "0xintro…",
    "base_url": "https://introducer.example"
  },
  "items": [ { "schema": "veritas.peer.introduction.v1" } ],
  "count": 1,
  "cap": 32,
  "central_network": false,
  "note": "public-URL-only; pull-only; not a registry; not the local peer book"
}
```

`introducer.base_url` is included only when it itself is a public HTTP(S)
URL (same filter as items). Otherwise omit the key. Do not invent
`VERITAS_PUBLIC_URL`. If the commerce wallet is missing, return
`items: []` with a note — do not 500.

No `POST /v1/peer/introductions`. No body. No gossip.

### Introduction record

One item: a signed statement *this node connected to that public URL*.

```json
{
  "schema": "veritas.peer.introduction.v1",
  "message_version": "veritas-peer-intro-v1",
  "introduced_base_url": "https://other.example",
  "introduced_did_pkh": "did:pkh:eip155:84532:0xother…",
  "introduced_commerce_address": "0xother…",
  "tls_fingerprint": "sha256:…",
  "connected_at": "2026-08-16T00:00:00Z",
  "introducer_did_pkh": "did:pkh:eip155:84532:0xintro…",
  "message": "veritas-peer-intro-v1\nintroduced_base_url: https://other.example\nintroduced_did_pkh: did:pkh:eip155:84532:0xother…\nintroduced_commerce_address: 0xother…\ntls_fingerprint: sha256:…\nconnected_at: 2026-08-16T00:00:00Z\nintroducer_did_pkh: did:pkh:eip155:84532:0xintro…",
  "signature": "0x…"
}
```

Canonical text, newline-joined, no trailing newline:

```
veritas-peer-intro-v1
introduced_base_url: <normalized public https URL, no trailing slash>
introduced_did_pkh: did:pkh:<network>:<lowercase address>
introduced_commerce_address: 0x<lowercase>
tls_fingerprint: sha256:<64 lowercase hex>
connected_at: <ISO-8601 UTC with Z, the book's connected_at>
introducer_did_pkh: did:pkh:<network>:<lowercase address>
```

`signature` is EIP-191 `personal_sign` by **this** node's commerce key.
Recovery must equal the introducer's `commerce_address`.

Omit any book row that lacks a public `base_url`, a `tls.fingerprint`,
or a `did_pkh` / `commerce_address`. Do not introduce HTTP-only or
LAN-only peers.

#### Publish filter (mandatory, both sides)

A URL may appear in `items` only if **every** resolved address passes
`veritas.peer._address_allowed(address, allow_local=False)`:

- refuse loopback, RFC1918 / unique-local, link-local, multicast,
  reserved, unspecified
- refuse cloud metadata (`169.254.169.254`, `100.100.100.200`) and
  any other link-local
- scheme must be `https` (introductions are WAN; LAN uses mDNS)
- if DNS fails, skip the row — do not publish an unverified host

The consumer re-runs the same filter before `connect`, even if the
introducer already did.

#### Cap and order

```
INTRO_CAP = 32
INTRODUCTIONS_PATH = "/v1/peer/introductions"
```

Newest `connected_at` first. Dedup by `normalize_base_url`; keep the
newest. Truncate to 32 **after** filter and dedup. `count` is
`len(items)` after the cap. `cap` is always 32.

---

## Connect verification

Extend `veritas.peer.connect`. Do not replace the SSRF guard.

### HTTPS + `tls` present (WAN default)

1. Existing `require_http_url` + `assert_connect_destination`.
2. Open TLS **without** the public CA bundle. Capture the presented
   peer certificate DER. This is pin-then-bind, not TOFU-on-CA.
3. `GET {base}/v1/peer` as today.
4. Refuse `tls_required` if the card omits `tls` **and**
   `allow_local` is false.
5. `presented_fp = sha256: + hex(SHA256(presented_der))`.
   Refuse `tls_mismatch` unless `presented_fp == card.tls.fingerprint`.
6. Reconstruct the binding message from card fields. Refuse
   `tls_unbound` unless it equals `card.tls.message`.
7. Recover `tls.binding`. Refuse `tls_unbound` unless the signer
   equals `card.commerce_address` (lowercase).
8. Refuse `tls_unbound` unless presented cert SAN URI ==
   `card.tls.san_uri` == `card.did_pkh` ==
   `did:pkh:{network}:{commerce_address}`.
9. Persist the book row as today, including the `tls` block.

### Expected pin (introductions)

When the caller already has an introduction, pass
`expected_fingerprint` and `expected_commerce_address` into `connect`.
Refuse `tls_mismatch` if the presented cert or recovered signer
disagrees **before** trusting the card body. This is the anti-replay
check: a replayed intro to a hijacked host fails unless the hijacker
also has the commerce key.

### HTTP / no `tls`

Allowed only with `--allow-local` (today's LAN path). WAN without
`tls` is `tls_required`. If `--allow-local` **and** `tls` is present,
still verify fingerprint + binding.

### New structured codes

| `code` | When |
|--------|------|
| `tls_required` | WAN connect, card has no `tls` |
| `tls_mismatch` | presented DER ≠ card (or expected) fingerprint; or SAN URI ≠ card |
| `tls_unbound` | message mismatch, bad signature, or recovered signer ≠ commerce address |

Existing `refused` / `unreachable` / `unparseable` stay.

---

## LAN: `_veritas._tcp`

Work package `peer_mdns`. Optional.

| Item | Locked value |
|------|----------------|
| Service type | `_veritas._tcp.local.` |
| Instance | `agent_id` if set, else first 12 hex chars of `identity_hash` |
| Port | `VERITAS_PORT` (default 8000) |
| TXT `path` | `/v1/peer` |
| TXT `schema` | `veritas.peer.v1` |

Card URL is `{scheme}://{advertised-host}:{port}/v1/peer`. Scheme is
`https` when TLS material exists, else `http`.

```python
# import-optional; never a hard dependency
try:
    from zeroconf import Zeroconf  # noqa: F401
except ImportError:
    # advertise() and browse() are no-ops
    ...
```

`browse()` returns card URLs. It does **not** call `connect`. The
operator (or a later CLI) passes a URL to `connect(..., allow_local=True)`.
Auto-connect is forbidden. SSRF still runs. Metadata IPs stay refused.

---

## WAN: pull introductions

Work package `peer_intro`.

```
already-connected peer A
        │
        │  GET /v1/peer/introductions
        ▼
   verify each item.signature
   (recovers A's commerce address)
        │
        │  for each public https URL (≤ 32)
        ▼
   connect(url, expected_fingerprint=…, expected_commerce_address=…)
        │
        ▼
   now connected to B; B's introductions are a later explicit pull
```

- One GET = one hop. No recursive default.
- Verify signature **before** `connect`. Drop items that fail.
- Re-run the publish filter on the consumer.
- Do not write failed intros into `peers.json`.
- A later `veritas-agent pull-intros <peer>` (or equivalent) is the
  CLI. Do not add a background crawler.

There is no revocation list. An old intro to a still-bound host stays
valid; an old intro to a hijacked host fails live TLS+binding. That is
the threat-model answer, not a TODO.

---

## Serve HTTPS

Work package `serve HTTPS`.

`veritas.server.main` / `veritas-agent serve` load
`VERITAS_TLS_CERT` / `VERITAS_TLS_KEY` if set, else
`{agent_home}/tls/cert.pem` + `key.pem`. When both files exist, pass
them to uvicorn (`ssl_certfile`, `ssl_keyfile`). When they do not,
serve HTTP as today (loopback tests and `--allow-local` stay green).

Default bind remains `127.0.0.1:8000`. WAN reachability is still an
operator bind + published URL. Serving HTTPS does **not** set
`listed_on_registry` or `public_seller`.

Issue cert + binding on `veritas-agent adopt` / `init` / first serve
when `cryptography` and the commerce wallet are present. Re-issue and
re-bind when the cert is missing or expired. Do not rotate on every
boot (fingerprint would churn).

### Optional ACME (later, not this cut)

`VERITAS_TLS_DOMAIN` is reserved. If set in a future cut, an operator
may obtain a public-CA cert for that DNS name. The cert **still**
includes SAN URI `did:pkh:…`, and the card **still** carries
fingerprint + binding. Public CA is extra transport trust for browsers;
agent `connect` still pins the fingerprint and checks the binding.
Do not implement ACME now. Do not fail serve if the env var is unset.

---

## Threat model

| Threat | What happens | Locked mitigation |
|--------|----------------|-------------------|
| **MITM without binding** | Attacker presents their own self-signed cert and a card whose fingerprint matches *their* cert | Binding is EIP-191 by the commerce key. They cannot match a known `commerce_address`. First contact to a raw URL learns *some* wallet; introductions carry the expected address + fingerprint so the first hop is pinned |
| **Intro replay** | Attacker replays a valid old intro to a URL they now control | `connect` checks the **live** cert against `tls_fingerprint` and the **live** binding against `introduced_commerce_address`. Replay without both keys fails |
| **LAN leak** | Introductions ship RFC1918 / loopback / link-local, exposing topology and SSRF gadgets | Publish filter + consume filter. Book stays unpublished. mDNS is LAN-only and never copied into introductions |
| **Metadata IP** | Card or intro points at `169.254.169.254` / `100.100.100.200` | Existing `_METADATA_IPS` + link-local refuse, even with `--allow-local`. Intro filter uses `allow_local=False` |
| **Commerce key as TLS key** | Payment key sits in the TLS stack / PEM file | Forbidden. TLS is P-256; commerce is secp256k1. Separate files |
| **Global eclipse / DHT sybil** | Attacker floods a shared table | There is no shared table. Degree-bounded pull from peers you chose |
| **Cert CN spoof** | CN set to a famous `did:pkh` | CN is not checked. SAN URI + fingerprint + binding are |

Honesty: this does not hide the peer's IP. Introductions *are* public
URLs. Metadata here means cloud-metadata endpoints, not "no IP is
revealed." Anyone you introduce can be dialed. That is the product.

---

## What other agents implement

Four work packages. This document is the spec; do not open a fifth
architecture. Do not edit Mesh Runner.

| Package | Files | Does |
|---------|-------|------|
| **peer_tls** | **new** `veritas/peer_tls.py`; extend `veritas/peer.py` `build_peer_card` + `connect`; tests in `tests/test_peer.py` / `tests/test_peer_tls.py` | Issue P-256 cert + PEM files; fingerprint; canonical binding message; `issue_tls_binding` / `verify_tls_binding`; card `tls` block; connect pin + recover |
| **peer_mdns** | **new** `veritas/peer_mdns.py`; optional CLI browse later | `advertise()` / `browse()` on `_veritas._tcp`; no-op without `zeroconf`; never auto-connect; still `--allow-local` |
| **peer_intro** | **new** `veritas/peer_intro.py`; `GET /v1/peer/introductions` in `veritas/server.py`; hooks + `LLMS_TXT` + repo `llms.txt` (sync-tested) | Filter, cap 32, sign, serve; `pull_introductions` verifies then `connect`s with expected pin |
| **serve HTTPS** | `veritas/server.py` uvicorn SSL; `veritas-agent serve` / `up` | Load cert/key; HTTP remains the no-cert path; issue-on-adopt/init; `VERITAS_TLS_DOMAIN` reserved only |

Optional extra when implementing (not a hard dep):

```
tls = ["cryptography>=42"]
# zeroconf is import-optional; do not add a hard extra unless advertise is tested
```

Acceptance pins (implementers write these):

- fingerprint is SHA-256 of DER, prefix `sha256:`
- binding recovers the commerce address; tampered fingerprint fails
- TLS private key is not the commerce key
- WAN `connect` without `tls` → `tls_required`
- fingerprint mismatch → `tls_mismatch`
- bad binding → `tls_unbound`
- introductions contain no RFC1918 / loopback / link-local / metadata
- list length ≤ 32
- unsigned or unrecovered intro is dropped before `connect`
- no POST handler for introductions
- mDNS is a no-op when `zeroconf` is missing
- HTTP serve still works without certs

---

## Out of scope

- libp2p, DHT, Kademlia, gossipsub, mDNS-SD beyond `_veritas._tcp`
- Always-on relay, TURN, hole punching, NAT traversal
- Push, gossip, or automatic multi-hop crawl
- ACME / Let's Encrypt implementation
- Public CA as a substitute for `tls.binding`
- Serving `peers.json`
- Mesh Runner (`ecosystem_cycle`) as a product network
- Closing G13, mainnet settlement, invented money
- Setting `listed_on_registry` or `public_seller`
- ERC-8004, W3C-registered DID methods, SPIRE

A first public URL still enters the graph the same way a BitTorrent
peer does: someone tells you, mDNS finds a LAN neighbor, or an
operator publishes `VERITAS_PUBLIC_URL`. This design removes the
**always-on central host**, not the need for one bootstrap URL.
