---
description: Look up any Solana token by mint address. Use it when someone asks what a Solana token or coin is, who created it and where (pump.fun, Raydium LaunchLab, Meteora, Moonshot), its price or price history, all-time high, pools and liquidity, largest holders, mint or freeze authority, Token-2022 extensions, or risk signals. Read-only; reports facts and sources, never advice.
argument-hint: <mint address>
allowed-tools: Bash(mint *)
---

# mint: Solana token lookups

`mint <command> <mint>` prints one JSON object (`data`, `sources`, `missing`,
`partial`, `fetched_at`) and never interprets. You write the answer.

| Question | Run |
| --- | --- |
| What is it? Overall picture and risk signals | `mint risk <mint>` (runs the four below) |
| Supply, authorities, extensions, name | `mint overview <mint>` |
| Who made it, when, on which launchpad? | `mint origin <mint>` |
| Pools, liquidity, LP burned | `mint pools <mint>` |
| Largest holders, holder count | `mint holders <mint>` |
| Price over time, highs and lows | `mint history <mint> --interval 1h --limit 168` |
| Creator's other coins, did the creator sell? | `mint creator <mint>` |

If the user typed `/mint:check` with an address ($ARGUMENTS), run
`mint risk $ARGUMENTS` and give a short, plain summary: what the token is,
where and when it was made, liquidity, holders, the signals found, and what
could not be checked. Add `mint history` only when price matters.

Read `${CLAUDE_PLUGIN_ROOT}/references/reading-results.md` before explaining
a field or a signal for the first time in a conversation.

## Wording rules

- Facts and signals only. Never say buy, sell, safe, scam, legit, or predict a
  price. Do not rank or score the token.
- A signal is evidence, not a verdict. "The mint authority is revoked" does
  not mean the token is safe. "Found" means the condition was seen, nothing more.
- Always give the mint address and the lookup time (`fetched_at`).
- Name the sources, and say plainly what is in `missing` and why.
- Never call `range_high` or `range_low` an all-time high or low unless
  `covers_full_history` is `true`. Otherwise give the date range it covers.

## Use calls sparingly

- Run each command at most once per token per question. Reuse earlier output.
- Ask the user before looking up more than 3 tokens in one go.
- If a result says a budget or safety cap was hit, stop and tell the user.
  Do not retry or loop. The budget resets within the hour.

## Keys

Never ask for a key, never accept one pasted into the conversation, and never
read the keys file. If a user offers a key, tell them to remove it from the
chat and use `/mint:setup` instead. Everything works without keys; a private
`SOLANA_RPC_URL` adds holder lists, because the public RPC refuses that call.
