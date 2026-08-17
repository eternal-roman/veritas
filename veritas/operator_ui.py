"""Local operator viewer and loopback enroll.

GET /ui is human HTML (excluded from the hooks registry). GET /v1/operator
is the same snapshot as JSON. POST /v1/operator/enroll writes the local
account and is loopback-only. This is not an account server.
"""

from __future__ import annotations

from typing import Any

from starlette.requests import Request

from veritas import __version__
from veritas.agent_account import catalog_document, enroll_account, whoami_document
from veritas.payment_config import get_payment_config
from veritas.pricing import current_price_point

LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost", "testclient"})


def is_loopback_client(request: Request) -> bool:
    host = ((request.client.host if request.client else "") or "").lower()
    return host in LOOPBACK_HOSTS or host.startswith("127.")


def public_account() -> dict[str, Any]:
    """whoami document for the operator viewer."""
    return dict(whoami_document())


def operator_snapshot() -> dict[str, Any]:
    from veritas.store import store_mode

    cfg = get_payment_config()
    return {
        "service": "veritas",
        "version": __version__,
        "store_mode": store_mode(),
        "payment": {
            **cfg.as_dict(),
            "pricing": current_price_point(cfg.price, cfg.network),
        },
        "account": public_account(),
        "catalog": catalog_document(),
        "ui": "/ui",
        "enroll": {
            "method": "POST",
            "path": "/v1/operator/enroll",
            "access": "loopback",
            "cli": "veritas-agent enroll",
        },
        "note": (
            "Viewer of existing config. Enroll is loopback-only. "
            "Funding the commerce wallet and public TLS stay external."
        ),
    }


def enroll_from_body(body: dict[str, Any]) -> dict[str, Any]:
    return enroll_account(
        agent_id=body.get("agent_id"),
        role=body.get("role"),
        interests=body.get("interests"),
    )


OPERATOR_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Veritas operator</title>
<style>
:root { color-scheme: dark; --ink:#e8e4d9; --mute:#9a9486; --line:#3a382f; --bg:#14130f; --card:#1d1b16; --acc:#d4a017; --bad:#c45c4a; --ok:#7a9e6a; }
* { box-sizing: border-box; }
body { margin:0; font: 15px/1.45 "IBM Plex Sans", "Segoe UI", sans-serif; background:var(--bg); color:var(--ink); }
header { padding:1.25rem 1.5rem; border-bottom:1px solid var(--line); display:flex; justify-content:space-between; gap:1rem; flex-wrap:wrap; }
h1 { font: 600 1.05rem/1 "IBM Plex Mono", ui-monospace, monospace; margin:0; letter-spacing:.04em; }
h1 span { color:var(--acc); }
main { display:grid; gap:1rem; padding:1.25rem 1.5rem 2rem; max-width:56rem; }
section { background:var(--card); border:1px solid var(--line); padding:1rem 1.1rem; }
h2 { margin:0 0 .6rem; font-size:.78rem; letter-spacing:.12em; text-transform:uppercase; color:var(--mute); }
dl { margin:0; display:grid; grid-template-columns:9rem 1fr; gap:.25rem .75rem; }
dt { color:var(--mute); } dd { margin:0; word-break:break-all; font-family:ui-monospace,monospace; font-size:.86rem; }
form { display:grid; gap:.55rem; max-width:28rem; }
label { display:grid; gap:.2rem; font-size:.82rem; color:var(--mute); }
input { background:#0e0d0a; color:var(--ink); border:1px solid var(--line); padding:.45rem .55rem; font: inherit; }
button { justify-self:start; background:var(--acc); color:#14130f; border:0; padding:.5rem .9rem; font:600 .85rem/1 inherit; cursor:pointer; }
.note, #msg { color:var(--mute); font-size:.85rem; }
#msg.err { color:var(--bad); } #msg.ok { color:var(--ok); }
.skills { display:flex; flex-wrap:wrap; gap:.35rem; }
.skills i { font-style:normal; border:1px solid var(--line); padding:.1rem .4rem; font-size:.78rem; }
a { color:var(--acc); }
</style>
</head>
<body>
<header>
  <h1>VERITAS <span>catalog</span></h1>
  <p class="note">Local viewer of this node's Kalshi/Polymarket store. Enroll is loopback-only. Not an account server.</p>
</header>
<main>
  <section>
    <h2>Instance</h2>
    <dl id="inst"></dl>
  </section>
  <section>
    <h2>Account</h2>
    <dl id="acct"></dl>
    <p id="skills" class="skills"></p>
  </section>
  <section>
    <h2>Enroll / refresh</h2>
    <form id="enroll">
      <label>Agent id <input name="agent_id" placeholder="self" autocomplete="off"></label>
      <label>Role <input name="role" placeholder="agent" autocomplete="off"></label>
      <label>Interests <input name="interests" placeholder="signals,verify" autocomplete="off"></label>
      <button type="submit">Write account.json</button>
    </form>
    <p id="msg" class="note">Same as <code>veritas-agent enroll</code>. Visa stays off this page.</p>
  </section>
</main>
<script>
function row(dl, k, v) {
  const dt = document.createElement("dt"); dt.textContent = k;
  const dd = document.createElement("dd"); dd.textContent = v == null || v === "" ? "—" : String(v);
  dl.append(dt, dd);
}
function paint(s) {
  const inst = document.getElementById("inst"); inst.replaceChildren();
  const p = s.payment || {};
  row(inst, "version", s.version);
  row(inst, "mode", p.mode);
  row(inst, "network", p.network);
  row(inst, "price", p.price);
  row(inst, "pay_to", p.pay_to);
  const acct = document.getElementById("acct"); acct.replaceChildren();
  const a = s.account || {};
  row(acct, "enrolled", a.enrolled);
  row(acct, "agent_id", a.agent_id);
  row(acct, "did", a.did);
  row(acct, "role", a.role);
  const commerce = (a.wallets && a.wallets.commerce) || {};
  row(acct, "commerce", commerce.address);
  const sk = document.getElementById("skills"); sk.replaceChildren();
  for (const x of (a.skills || [])) {
    const i = document.createElement("i");
    i.textContent = x.mapped ? x.id : (x.id + "?");
    sk.append(i);
  }
  if (!a.enrolled) {
    const n = document.createElement("span");
    n.className = "note";
    n.textContent = a.next || "veritas-agent enroll";
    sk.append(n);
  }
}
async function load() {
  const r = await fetch("/v1/operator");
  paint(await r.json());
}
document.getElementById("enroll").addEventListener("submit", async (e) => {
  e.preventDefault();
  const fd = new FormData(e.target);
  const body = {};
  for (const [k, v] of fd.entries()) if (String(v).trim()) body[k] = String(v).trim();
  const msg = document.getElementById("msg");
  const r = await fetch("/v1/operator/enroll", {
    method: "POST", headers: {"content-type": "application/json"},
    body: JSON.stringify(body)
  });
  const data = await r.json();
  if (!r.ok) {
    msg.className = "err";
    msg.textContent = data.detail || data.error || r.status;
    return;
  }
  msg.className = "ok";
  msg.textContent = "enrolled " + (data.agent_id || "") + " · " + (data.binding_hash || "").slice(0, 16);
  load();
});
load();
</script>
</body>
</html>
"""
