# Public TLS host

Strangers cannot find a seller until an operator publishes an HTTPS
URL. This repository does **not** claim a live host. The files next to
this note are the operator runbook.

What this environment cannot do: hold a Fly/Railway/Cloudflare/Vercel
token, own a domain, or fund the pay-to wallet. Those stay human steps
(constitution A21).

## What "public" means here

1. An HTTPS origin a stranger agent can dial without a VPN.
2. `VERITAS_PUBLIC_URL` set to that origin (live mode refuses relative
   resource URLs).
3. `VERITAS_PAY_TO` a funded USDC address.
4. `VERITAS_REQUIRE_PAYMENT=true` and a real facilitator
   (`https://x402.org/facilitator` is the one that has settled in
   operator-run testnet arcs).

Until all four are true, `listed_on_registry` stays false and
`adopt.json` carries `public_seller: null`.

## Option A — Fly.io (TLS included)

`deploy/fly.toml` pins the process to `0.0.0.0:8000`, matching the
image (`Dockerfile` `VERITAS_PORT=8000`, `EXPOSE 8000`). Fly
terminates TLS on the shared certificate for `*.fly.dev`.

```bash
fly apps create veritas-signals   # once
fly volumes create veritas_runtime --region ord --size 1
fly secrets set \
  VERITAS_REQUIRE_PAYMENT=true \
  VERITAS_PAY_TO=0xYourWallet \
  VERITAS_PUBLIC_URL=https://veritas-signals.fly.dev \
  VERITAS_NETWORK=eip155:84532 \
  VERITAS_FACILITATOR=https://x402.org/facilitator \
  VERITAS_RUNTIME_DIR=/data/runtime
fly deploy --config deploy/fly.toml --dockerfile Dockerfile
```

A volume is required: receipts, ledger, and signal snapshots are
durable state. Without one they vanish on every machine replace.

## Option B — Caddy in front of the container

`deploy/Caddyfile` is a reverse proxy that obtains a Let's Encrypt
certificate for a domain you already control. Point DNS at the host,
then:

```bash
docker compose up -d
caddy run --config deploy/Caddyfile
```

Caddy proxies `127.0.0.1:8000` (the compose publish). Caddy is the
hardened default (automatic HTTPS, HTTP/2, no custom TLS stack in
this repo). Do not terminate TLS in Python.

## After it is up

```bash
curl -sS https://YOUR_HOST/readyz
curl -sS https://YOUR_HOST/.well-known/x402
veritas-diligence https://YOUR_HOST
veritas-buy https://YOUR_HOST
```

`/readyz` must be 200 before any registry listing. A 503 means the
runtime directory cannot be written or payment config is
misconfigured — that is the process telling you not to route to it.

## What this still is not

- Not a live host. This file is a runbook, not a URL.
- Not mainnet. Default network is Base Sepolia.
- Not unsolicited demand. Listing the URL is the next human step.
- Not a proof that the local facilitator settled. Live mode uses the
  configured facilitator.
