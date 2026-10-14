# Reading results

What each field and signal means, and what it does not mean.

## Every result

| Field | Meaning |
| --- | --- |
| `mint` | The token's mint address. Always repeat it in the answer. |
| `fetched_at` | When the lookup ran (UTC). On-chain state can change right after. |
| `sources` | Every service the script read, by host. |
| `missing` | What could not be checked, and why. Report these. |
| `partial` | `true` when something that should have been there could not be fetched. |

## overview

- `mint_authority`: the address that can mint more tokens. `null` means
  revoked: nobody can ever mint more.
- `freeze_authority`: the address that can freeze any holder's token account.
  `null` means revoked. Stablecoins such as USDC keep one on purpose.
- `token_program`: `SPL Token` (classic) or `Token-2022` (supports extensions).
- `extensions`: Token-2022 features built into the mint. See the risk signal below.
- `metadata.is_mutable` with an `update_authority`: the name, symbol and image
  link can still be changed by that address.
- `supply`: whole tokens, decimals applied. `supply_raw` is the integer on chain.

## origin

- `created_at`, `creator`: time and fee payer of the oldest successful
  transaction that touched the mint. The fee payer is usually, not always, the
  person who launched it; launch bots and services can pay instead.
- `launchpad`: matched from the programs in that transaction against
  `launchpads.md`. `null` means no listed program was found, not that there
  was no launchpad.
- `reached_creation: false`: the history was too long to page through. The
  creation fields are empty and `oldest_seen_at` is only a lower bound.
- `creator_prior_tx_count`: transactions the creator sent before the
  creation, counted up to 1,000 (`..._capped: true` means 1,000 or more).

## history

- `scope`: `token, all pools` (Birdeye) or `most liquid pool` (GeckoTerminal).
  A single pool can differ from the overall price, especially for thin pools.
- `change_pct`: first close to last close in the returned candles only.
- `range_high`, `range_low`: the highest and lowest price in the returned
  candles. They are all-time values only when `covers_full_history` is `true`.
- `covers_full_history`: `true` when the candles start within one interval of
  the pool's creation; `false` when they start later (GeckoTerminal's free API
  stops at 180 days); `null` when the pool's creation time is unknown. On the
  free path it covers one pool only: a graduated coin traded on its bonding
  curve before that pool existed, and that trading is not included.
- `market_cap_usd`, `fdv_usd`: current values from GeckoTerminal. Past market
  cap is not available; it is not close multiplied by today's supply.

## Budget errors

Every request counts against a shared budget: 200 requests per source per
hour by default (`MINT_MAX_CALLS_PER_HOUR`), and at most 150 per script
run. An error saying the budget is used up is a safety stop, not a source
failure. Stop and tell the user; it resets within the hour.

## pools

- `lp_model`:
  - `LP token`: liquidity providers hold a token for their share. Who holds
    it decides who can withdraw.
  - `positions`: concentrated liquidity (Raydium CLMM, Orca, Meteora DLMM and
    DAMM v2). No LP token; "burned LP" does not apply.
  - `bonding curve`: the token is still on its launchpad curve; liquidity sits
    in the launchpad program.
- `lp_note: all burned (supply 0)`: every LP token was burned. Nobody can
  withdraw that liquidity with LP tokens.
- `lp_at_burn_address_pct`: share of LP tokens held by the incinerator address.
  LP burned with the Burn instruction lowers supply instead and cannot be
  measured here. Lockers (time-locked LP) are not detected yet.

## holders

- `share_pct`: share of current supply in that token account.
- `owner_kind: program account`: the owner is a program or a program-derived
  address: a pool, vault, bonding curve or locker. Not a person.
- `top10_wallets_share_pct`: the ten largest wallet owners, program accounts
  excluded. One person can hold many wallets, and an exchange wallet holds for
  many people; this number shows neither.
- `holder_count` and `distribution_pct` come from GeckoTerminal, include pools,
  and may be hours old (`distribution_updated_at`).

## risk signals

Each signal has `status`: `found`, `not found`, `not checked` or
`not applicable`, plus `evidence` and, where a line had to be drawn, `threshold`.

| Signal | Found means | It does not mean |
| --- | --- | --- |
| `mint_authority_live` | An address can mint more tokens. | That it will. Many legitimate tokens keep it. |
| `freeze_authority_live` | An address can freeze holders' accounts. | That it will. Regulated stablecoins keep it. |
| `token2022_extensions` | The mint has a permanent delegate, transfer hook, transfer fee, non-transferable flag, frozen default state, close authority or pause. | That it is misused. PYUSD has several for compliance. |
| `metadata_editable` | Name, symbol or image link can still change. | That they will change. |
| `holder_concentration` | The top 10 wallets hold 30% or more (program accounts excluded). | That holders will sell, or that they are insiders. |
| `liquidity_unlocked` | In the most liquid pool, less than 90% of LP tokens sit at the burn address. | That liquidity will be pulled. LP may be in a locker this skill cannot see. |
| `new_creator_wallet` | The creator was first seen less than 24 hours before creation. | Bad intent. Many people use fresh wallets for privacy. |

`not found` only covers what was checked: "the mint authority is revoked" is
one fact, not a clean bill of health.
