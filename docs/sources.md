# Data sources

What each source is used for, its endpoints, limits and terms, and when that
was checked. Re-check before a release and update the date.

Last full check: **2026-10-14**.

## Solana public RPC

- **Used by:** every lookup when `SOLANA_RPC_URL` is not set.
- **Endpoints:** `https://api.mainnet-beta.solana.com` (also served as
  `api.mainnet.solana.com`).
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
- **Also used by:** `creator.py`, on the creator wallet: `type=CREATE` with
  `before-signature` paging (the creator's coins), and `sort-order=asc` with
  `gt-time` (activity after creation). Tested on mainnet 2026-10-15.
- **Credits** (helius.dev/docs/billing/credits, 2026-10-15): Enhanced
  Transactions cost 100 credits per call (the page calls it legacy, in
  maintenance mode; Parsed Events at 10 credits is named as its successor).
  So the free plan covers about 10,000 calls a month. `/mint:creator` makes
  3 to 7 such calls.
- **Exercised with a real key on 2026-10-15** (origin and creator lookups).
  Pump.fun creations come back as type `CREATE`, source `PUMP_FUN`; a
  Streamflow lock can also be typed `CREATE`.

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
- **History depth:** the keyless API only serves the past 180 days. Asking
  for older candles with `before_timestamp` returns 401: "You can only access
  data from the past 180 days with Public API" (tested 2026-10-15). A request
  for 1,000 daily candles quietly returns about 183.
- **Limits:** 30 calls/min for the keyless API (GeckoTerminal FAQ and CoinGecko
  help centre, 2026-10-14). No authentication.
- **Terms:** the keyless API is covered by CoinGecko's API terms
  (coingecko.com/en/api_terms; blocked to automated fetch on 2026-10-14, so
  re-read in a browser). No attribution requirement was found in the docs.
- **Tested 2026-10-14:** all three endpoints answered; heavy use in a short
  burst returned 429. The backoff waits 2+4+8+16+30 s, a full minute, before giving up.

## DEX Screener (free, no key)

- **Used by:** `pools.py`, and `creator.py` for the creator's coins.
- **Endpoints:** `GET https://api.dexscreener.com/token-pairs/v1/solana/{mint}`;
  `GET /tokens/v1/solana/{mint1,mint2,...}` (pairs for many mints in one call;
  the docs page states no limit, a 22-address call worked 2026-10-15)
  (docs.dexscreener.com/api/reference).
- **Limits:** not stated for this endpoint on 2026-10-14; other endpoints list
  60/min, pair endpoints are commonly 300/min.
- **Terms** (docs.dexscreener.com/api/api-terms-and-conditions, updated
  2023-08-18): commercial and non-commercial use allowed; no reselling or
  building a direct competitor; no attribution clause.
- **Note:** requests with Python's default user agent get 403. Scripts send
  `mint-solana/<version>`.

## mint-data (dropped)

- Our own sampled dataset of new pump.fun coins, read by `outcomes.py` in
  0.4.0. Dropped on 2026-10-15: a sample of 25 coins per 6 hours was too
  thin, collecting every coin needs a paid Helius plan, and Helius's terms
  (updated 2026-04-24) forbid making its products available to third
  parties. The repo is private and its workflow disabled. `/mint:outcomes`
  now uses only the user's own samples.

## Dune (considered for v0.4.0, not used yet)

- **Planned use:** historical base rates ("of N similar coins, M ...") from
  SQL over Solana and pump.fun tables.
- **API access** (docs.dune.com pricing FAQ and api-reference rate-limits
  page, 2026-10-15): "Free access after the trial is view-only and does not
  include API access." API use needs a 14-day trial (2,500 credits) or a paid
  plan. An older Dune blog post says free users get the API; the current docs
  say otherwise.
- **Cost:** no fixed rate per execution; credits follow the compute a query
  uses. Result rows also cost credits.
- **Terms** (dune.com/sql-api-terms, last updated 2026-05-13): no use that
  substitutes for the service or competes with Dune; keys must not be put in
  public repositories or client code. Showing results to end users is not
  addressed.
- **Status:** not usable by default, since keyless users get nothing. Waiting
  on the owner's decision.

## Artist Passport

Removed in v0.2.0 (2026-10-15): of little value to most users.

## Similar tools (checked 2026-10-14)

MCP servers exist for Solana token risk: kukapay/rug-check-mcp (wraps the
Solsniffer API, needs its key), Noesis (hosted, holder analysis), and hosted
rug-check endpoints. No Claude Code skill was found. This one differs: it runs
locally on free sources with optional keys, shows its sources and gaps,
reports facts instead of a score, and caps its own request rate.
