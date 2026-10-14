# solana-token-intel: plan

An open-source Claude Code skill that lets Claude look up the history and
make-up of any Solana token: what it is, who made it and where, how its price
and liquidity developed, who holds it, and which risk signals it shows. Each
user brings their own RPC URL and API keys; nothing runs on a server of ours.

## Why this exists

Claude cannot answer "what is this coin?" on its own today: it has no access
to on-chain data or market history. People check tokens by hand across an
explorer, a chart site and a holder list. A skill with small scripts can do
that in one step and explain what it finds in plain, neutral language.

It also spreads riff's Artist Passport: every lookup shows whether a verified
artist endorses or disavows the coin.

## Step 0: verify before building

- Read the current Claude Code docs on skills and plugins (SKILL.md
  frontmatter, bundled scripts, plugin packaging).
- For every data source below, check the current endpoints, rate limits, free
  tiers and terms of use. Record what was checked and when in
  `docs/sources.md`. Drop any source whose terms forbid this use.
- Check whether similar skills or MCP servers already exist and how this one
  differs.

## How it works

```
solana-token-intel/
  SKILL.md              when to use it, which script answers what, how to word results
  scripts/
    common.py           config from env, HTTP with retries, JSON output, no key logging
    overview.py         mint account: supply, decimals, authorities, Token-2022 extensions, metadata
    origin.py           first transactions of the mint: created when, by whom, via which program
    history.py          price, volume and market cap candles over time
    pools.py            pools, liquidity per pool, LP supply burned or not
    holders.py          largest holders and their share of supply
    risk.py             combines the above into risk signals
    endorsement.py      Artist Passport endorsements for a mint
  references/
    reading-results.md  what each field and signal means, and what it does not mean
    launchpads.md       program IDs used to detect where a token was launched
  .env.example
  README.md, LICENSE (MIT)
```

- Scripts use the Python standard library only, so there is nothing to install.
- Every script prints one JSON object: the data, its sources, and a timestamp.
- Claude runs the scripts it needs and writes the answer; the scripts never
  interpret.

## Keys: bring your own, with free fallbacks

| Variable | Used for | Without it |
| --- | --- | --- |
| `SOLANA_RPC_URL` | Mint, holders, transactions | Public mainnet RPC: works, but slow and rate-limited |
| `HELIUS_API_KEY` (or another indexer) | Full, parsed transaction history for origin lookups | Origin limited to what plain RPC paging can find |
| `BIRDEYE_API_KEY` | Detailed price history | Free public price sources only |

Rules:

- Keys come from environment variables or a `.env` file that git ignores.
- Claude never asks a user to paste a key into the conversation; the skill
  says so explicitly and explains how to set the variable instead.
- No script prints, logs or returns a key, including in error messages and
  URLs.
- Every script states which sources it used, so the user knows how complete
  the answer is.

## What each script returns

- **overview**: mint address, supply, decimals, mint authority, freeze
  authority, token program (SPL or Token-2022), extensions, name, symbol, URI,
  metadata update authority.
- **origin**: creation time, creator wallet, creating program, and the
  launchpad name if the program is known.
- **history**: candles (open, high, low, close, volume) for a chosen interval
  and range; first and last trade seen.
- **pools**: each pool with its program, liquidity, and the share of LP tokens
  burned or held.
- **holders**: top holders with amounts and shares; flags for known program
  accounts (pools, vaults) so they are not mistaken for people.
- **risk**: signals with the evidence behind each: live mint or freeze
  authority, risky Token-2022 extensions, editable metadata, concentrated
  holders, unlocked liquidity, very new creator wallet.
- **endorsement**: endorsed, disavowed or no record, for each Artist Passport
  that has an entry for this mint, with the passport's age. Mainnet support
  starts when the passport program is deployed there; devnet until then.

## Wording rules (in SKILL.md)

- Facts and signals, never advice: no "buy", "sell", "safe" or price
  predictions.
- A signal is not a verdict: "the mint authority is revoked" does not mean
  "the token is safe".
- Say what could not be checked and why (missing key, rate limit, unknown
  launchpad).
- Always give the token's mint address and the time of the lookup.

## Milestones

1. **Step 0** checks, written down in `docs/sources.md`.
2. **common.py** and **overview.py**, working with the public RPC only.
3. **holders.py**, **pools.py**, **history.py** with free sources.
4. **origin.py** with plain RPC, improved when an indexer key is set.
5. **risk.py** and **references/reading-results.md**.
6. **endorsement.py** against the Artist Passport on devnet.
7. **SKILL.md** with a precise description, then a trial on 20 real tokens:
   new pump.fun coins, graduated coins, well-known tokens, a known rug.
8. **Release** on GitHub under MIT, installable as a Claude Code plugin; a
   short X thread with one example lookup.
9. **Later**: an MCP server that wraps the same scripts, for the Claude
   desktop and web apps.

## Open questions (decided 2026-10-14)

- Which indexer first? Helius (`HELIUS_API_KEY`, enhanced transactions, oldest first).
- How far back does `origin.py` page with plain RPC? 10 pages of 1,000
  signatures by default, `--max-pages` to change; past that it reports the
  oldest transaction seen and says the creation was not reached.
- Local cache? Not for now; results are always fresh.
