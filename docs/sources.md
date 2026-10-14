# Data sources

What each source is used for, its endpoints, limits and terms, and when that
was checked. Re-check before a release and update the date.

Last full check: **2026-10-14**.

## Solana public RPC

- **Used by:** every script without `SOLANA_RPC_URL`; `endorsement.py` on devnet.
- **Endpoints:** `https://api.mainnet-beta.solana.com` (also served as
  `api.mainnet.solana.com`), `https://api.devnet.solana.com`.
- **Limits** (solana.com/docs/references/clusters, 2026-10-14): 100 requests
  per 10 s per IP, 40 per 10 s for one method, 40 connections, 100 MB per 30 s.
- **Terms:** "not intended for production applications"; IPs can be blocked
  without notice. Fine for occasional personal lookups, which is this tool.
- **Tested 2026-10-14:** `getTokenLargestAccounts` returns HTTP 429 on every
  call, on mainnet and devnet, while other methods return 200. So holder lists
  and LP holders need a private RPC. Free keyless RPCs tried (PublicNode, dRPC,
  Ankr) also refuse it.

## Helius (optional, `HELIUS_API_KEY`)

- **Used by:** `origin.py`, for the oldest transactions of a mint in one call.
  Also a good `SOLANA_RPC_URL` (its RPC serves holder lists).
- **Endpoint:** `GET https://api-mainnet.helius-rpc.com/v0/addresses/{address}/transactions?api-key=…&sort-order=asc&limit=10`
  (helius.dev/docs, Enhanced Transactions: `sort-order` asc|desc, `limit` 1–100,
  `before-signature`, `gt-time` and others).
- **Limits** (helius.dev/docs/billing/plans, 2026-10-14): free plan 1M credits
  a month, 10 requests/s.
- **Terms:** helius.dev/terms (page reachable 2026-10-14). Users bring their own
  key and plan.
- **Not exercised with a real key.** A request without a key returns 401, which
  confirms the endpoint exists; the response parsing follows the docs.

## Birdeye (optional, `BIRDEYE_API_KEY`)

- **Used by:** `history.py`, for candles across all pools.
- **Endpoint:** `GET https://public-api.birdeye.so/defi/ohlcv?address=…&type=1H&time_from=…&time_to=…`,
  headers `X-API-KEY` and `x-chain: solana`. Response `data.items[]` with
  `o h l c v unixTime`.
- **Limits:** the free tier is about 1 request/s. Whether plain `/defi/ohlcv`
  is in the free tier was unclear on 2026-10-14 (the rate-limit page and a
  2025 changelog disagree). If it is not, `history.py` falls back to
  GeckoTerminal and says so.
- **Terms:** birdeye.so/terms (blocked to automated fetch on 2026-10-14; read it
  in a browser before relying on Birdeye).
- **Not exercised with a real key.** Without a key: 401.

## GeckoTerminal (free, no key)

- **Used by:** `history.py` (pools, candles, current price and market cap),
  `holders.py` (holder count and distribution).
- **Endpoints:** `https://api.geckoterminal.com/api/v2`
  - `/networks/solana/tokens/{mint}/pools?page=1`, ranked by GeckoTerminal
  - `/networks/solana/pools/{pool}/ohlcv/{day|hour|minute}?aggregate=…&limit=≤1000&currency=usd&token={mint}`
    (aggregate: day 1; hour 1, 4, 12; minute 1, 5, 15). Newest candle first.
  - `/networks/solana/tokens/{mint}/info`: `holders.count`, `distribution_percentage`
- **Limits:** 30 calls/min for the keyless API (GeckoTerminal FAQ and CoinGecko
  help centre, 2026-10-14). No authentication.
- **Terms:** the keyless API is covered by CoinGecko's API terms
  (coingecko.com/en/api_terms; blocked to automated fetch on 2026-10-14, so
  re-read in a browser). No attribution requirement was found in the docs.
- **Tested 2026-10-14:** all three endpoints answered; heavy use in a short
  burst returned 429. The backoff waits 2+4+8+16+30 s, a full minute, before giving up.

## DEX Screener (free, no key)

- **Used by:** `pools.py`.
- **Endpoint:** `GET https://api.dexscreener.com/token-pairs/v1/solana/{mint}`
  (docs.dexscreener.com/api/reference).
- **Limits:** not stated for this endpoint on 2026-10-14; other endpoints list
  60/min, pair endpoints are commonly 300/min.
- **Terms** (docs.dexscreener.com/api/api-terms-and-conditions, updated
  2023-08-18): commercial and non-commercial use allowed; no reselling or
  building a direct competitor; no attribution clause.
- **Note:** requests with Python's default user agent get 403. Scripts send
  `solana-token-intel/<version>`.

## Artist Passport (riff)

- **Used by:** `endorsement.py`.
- **IDL:** github.com/use-riff/riff, `idl/riff_passport.json`, copied to
  `skills/solana-token-intel/references/riff_passport.json` on 2026-10-14
  (version 0.1.0). Program `2nke6euXvAnbtdtcbbk8N2Z3SRLuR7i67VYmSdcY5kwj`.
- **Deployed:** devnet yes (executable, 2026-10-14); mainnet no.
- **Lookup:** `getProgramAccounts` with the `Endorsement` discriminator at
  offset 0 and the mint at offset 40, then the `Passport` accounts. Layouts are
  decoded from the IDL, so a new IDL version only needs the file replaced.

## Similar tools (checked 2026-10-14)

MCP servers exist for Solana token risk: kukapay/rug-check-mcp (wraps the
Solsniffer API, needs its key), Noesis (hosted, holder analysis), and hosted
rug-check endpoints. No Claude Code skill was found. This one differs: it runs
locally on free sources with optional keys, shows its sources and gaps,
reports facts instead of a score, and adds Artist Passport endorsements.
