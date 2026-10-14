---
name: solana-token-intel
description: Look up any Solana token by mint address. Use it when someone asks what a Solana token or coin is, who created it and where (pump.fun, Raydium LaunchLab, Meteora, Moonshot), its price history, pools and liquidity, largest holders, mint or freeze authority, Token-2022 extensions, risk signals, or whether a verified artist endorses or disavows it (riff Artist Passport). Read-only; reports facts and sources, never advice.
allowed-tools: Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/*)
license: MIT
---

# Solana token intel

Each script takes a mint address, prints one JSON object (`data`, `sources`,
`missing`, `partial`, `fetched_at`) and never interprets. You write the answer.

| Question | Run |
| --- | --- |
| What is it? Supply, authorities, extensions, name | `python3 ${CLAUDE_SKILL_DIR}/scripts/overview.py <mint>` |
| Who made it, when, on which launchpad? | `python3 ${CLAUDE_SKILL_DIR}/scripts/origin.py <mint>` |
| Price over time | `python3 ${CLAUDE_SKILL_DIR}/scripts/history.py <mint> --interval 1h --limit 168` |
| Pools, liquidity, LP burned | `python3 ${CLAUDE_SKILL_DIR}/scripts/pools.py <mint>` |
| Largest holders | `python3 ${CLAUDE_SKILL_DIR}/scripts/holders.py <mint>` |
| Risk signals (runs overview, origin, holders, pools) | `python3 ${CLAUDE_SKILL_DIR}/scripts/risk.py <mint>` |
| Artist Passport endorsements | `python3 ${CLAUDE_SKILL_DIR}/scripts/endorsement.py <mint>` |

For "what is this coin?", run `risk.py` and `endorsement.py`; add `history.py`
when price matters. Intervals: 1m 5m 15m 1h 4h 12h 1d. Exit code 1 means the
input was rejected; the reason is JSON on stderr.

Read `references/reading-results.md` before explaining a field or a signal
for the first time in a conversation.

## Wording rules

- Facts and signals only. Never say buy, sell, safe, scam, legit, or predict a
  price. Do not rank or score the token.
- A signal is evidence, not a verdict. "The mint authority is revoked" does
  not mean the token is safe. "Found" means the condition was seen, nothing more.
- Always give the mint address and the lookup time (`fetched_at`).
- Name the sources, and say plainly what is in `missing` and why (missing key,
  rate limit, unknown launchpad, devnet only).
- Endorsements come from devnet until the passport program is on mainnet; say so.

## Keys

Never ask for a key, and never accept one pasted into the conversation. If a
user offers one, tell them to remove it and use setup instead. Keys live in
environment variables or a private config file. To add them, the user runs
this in their own terminal (input is hidden):

```
python3 ${CLAUDE_SKILL_DIR}/scripts/cli.py setup
```

`cli.py doctor` checks every source. Without keys everything still runs;
holder lists need a private `SOLANA_RPC_URL`, because the public RPC refuses
that call.
