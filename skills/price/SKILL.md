---
description: Price history of a Solana token, with highs and lows.
argument-hint: <mint address> [1m|5m|15m|1h|4h|12h|1d]
allowed-tools: Bash(mint *)
disable-model-invocation: true
---

Run `mint history <mint> --interval <interval> --limit <n>` for the address in
"$ARGUMENTS". Default interval 1h with limit 168 (one week); for 1d use limit
1000. Summarize the current price, the change over the range, and the range
high and low with their dates.

Follow the wording rules of the `check` skill. Never call `range_high` an
all-time high unless `covers_full_history` is `true`; otherwise say which
dates the candles cover and why (the `missing` entry explains it).
