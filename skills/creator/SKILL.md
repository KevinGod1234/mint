---
description: Track record of a Solana token's creator, with their other coins and what they did with this one.
argument-hint: <mint address>
allowed-tools: Bash(mint *)
disable-model-invocation: true
---

Run `mint creator <mint>` for the address in "$ARGUMENTS". It makes 10 to 20
requests, so run it once per token.

Report:

- the creator wallet, when the coin was made and where
- how many coins this wallet created (`coins_found`) and how many have no
  pools listed now (`coins_without_pools`), with a few examples
- what the creator did with this coin: amount received, sold, sent to a pool
  and sent elsewhere, when relative to the peak (`hours_from_peak`), and what
  they hold now

Read the `creator` section of `${CLAUDE_PLUGIN_ROOT}/references/reading-results.md`
first. Follow the wording rules of the `check` skill. "The creator sent 97% of
what they received to the pool within a minute" is a fact. "This is a rug" is
not. Without `HELIUS_API_KEY` only the creator, the peak and the current
balance are available; say so and point to `/mint:setup`.
