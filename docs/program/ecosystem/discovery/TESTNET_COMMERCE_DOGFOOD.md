# Testnet multi-agent commerce dogfood — findings

**Date:** 2026-08-09  
**Network:** Base Sepolia (`eip155:84532`)  
**Faucet:** https://faucet.circle.com/ (USDC, 20 / address / 2h)  
**Tools:** `scripts/circle_faucet_playwright.py`, `scripts/dogfood_agent_commerce.py`,  
`.veritas_dogfood/` roster (gitignored testnet keys only)

---

## What we verified (this session)

| Check | Result | Evidence |
|-------|--------|----------|
| Wallet generation (buyer / seller / peer) | **OK** | `.veritas_dogfood/roster.json` — three `eth_account` keys |
| Public RPC `eth_chainId` | **OK** | `0x14a34` Base Sepolia |
| x402 facilitator `/supported` | **OK** | HTTP 200, exact + eip155:84532 v2 |
| ERC-20 USDC `balanceOf` probe | **OK** | USDC `0x036CbD…CF7e`; new wallets **0** |
| Playwright opens Circle faucet | **OK** | Network select + address fill work |
| Unattended faucet fund | **BLOCKED** | reCAPTCHA + “unusual traffic / not a bot” |
| Live-mode server without `VERITAS_PUBLIC_URL` | **misconfigured** | payment_config requires absolute resource URL |
| Live-mode with full env pack | **OK** | `payment_mode=live`, `live_ready=true` |
| Unpaid `POST /v1/research` | **402** + accepts | network `eip155:84532`, payTo=seller, USDC asset, amount 10000 |
| Buyer sign via `pay_via_policy` | **OK** | EIP-712; payer = dogfood buyer address |
| Facilitator verify (0 USDC balance) | **Honest refuse** | `invalid_exact_evm_insufficient_balance` → 402 (not invent settle) |
| End-to-end funded settle this session | **BLOCKED** (faucet captcha) | Need human `--headed --wait-human` fund |
| Prior project E2E (funded buyer) | **PROVEN** | `docs/program/fable/settlement/` · n=2 testnet · #112/#119 |

---

## How to complete fund → settle (operator minutes)

```powershell
# 1) Wallets already in .veritas_dogfood/ (or regenerate)
python -c "from eth_account import Account; ..."  # see roster

# 2) Fund buyer (human completes captcha in the window)
python scripts/circle_faucet_playwright.py `
  --address 0xYOUR_BUYER `
  --network "Base Sepolia" `
  --headed --wait-human 120

# 3) Confirm balance
# (script prints balance_after.usdc)

# 4) Live seller
$env:VERITAS_PAY_TO = "<seller 0x>"
$env:VERITAS_REQUIRE_PAYMENT = "true"
$env:VERITAS_NETWORK = "eip155:84532"
$env:VERITAS_FACILITATOR = "https://x402.org/facilitator"
$env:VERITAS_PRICE = "`$0.01"
$env:VERITAS_PUBLIC_URL = "http://127.0.0.1:8765"
$env:VERITAS_RPC_URL = "https://sepolia.base.org"
python -m uvicorn veritas.server:app --host 127.0.0.1 --port 8765

# 5) Buyer dogfood
python scripts/dogfood_agent_commerce.py --base-url http://127.0.0.1:8765
# or: BUYER_PRIVATE_KEY=... python scripts/testnet_settlement.py
```

Buyer needs **no ETH** for x402 exact (EIP-3009; facilitator pays gas).

---

## Vision: agents hold tokens and pay each other

**Target shape**

1. Each agent has a **wallet** + **budget** (USDC testnet now; mainnet later).  
2. Services advertise **price + falsifiability class** (community-visible).  
3. Buyers pay only under **SpendPolicy** (caps, network allowlist).  
4. **Community agreement of value** = published norms (constitution + price tables + warranties), not a chat handshake.

**What exists today**

| Layer | Status |
|-------|--------|
| Wallet mint | L1 (`veritas.autonomous.wallet` / eth_account dogfood) |
| Single-seller x402 research | L1-live (testnet n=2 prior) |
| SpendPolicy + payer journal | L1 |
| Multi-seller USDC peer A2A | Self-host connect exists; no public seller |
| Community rate card | **Missing** |
| Unattended faucet | **Blocked by captcha** |
| Unsolicited third-party buyer | **0** |

---

## Planned components (priority)

1. **Funding ops** — headed faucet recipe (done scripts); optional funded-wallet vault for CI-like dogfood (testnet only).  
2. **Live dogfood env pack** — required env including `VERITAS_PUBLIC_URL` (found this session).  
3. **Multi-agent roster runtime** — N agents, each with key + role + spend cap; run buyer↔seller swaps.  
4. **Community value surface** — machine-readable price + warranty on discovery; buyer policy matches.  
5. **Second seller process** — constitution export so another agent sells under same honesty stack.  
6. **Stage-1 public existence** — only path to unsolicited commerce.  
7. **W1 bond escrow** — after public money, verification becomes paid.

---

```
PROPERTY: faucet automation blocked by captcha; wallets+RPC+facilitator L1; settle path known but unfunded this run
EVIDENCE LEVEL: L1 (probes + faucet transcripts) / L0 (multi-agent USDC mesh plan)
NOT PROVEN: this-session on-chain tx; unattended faucet success; multi-seller USDC commerce
```
