# solana-token-intel

A Claude Code skill that looks up any Solana token: what it is, who made it
and where, how its price and liquidity developed, who holds it, which risk
signals it shows, and whether a verified artist endorses or disavows it
(riff Artist Passport).

It is read-only. It never signs or sends a transaction and never touches a
wallet. It reports facts with their sources, and says what it could not
check. It does not give advice.

```
you    what is A1cNG1fuMuJjwmEKEwMyeVQcxgkk2GyjuBns9znUpump?
claude A pump.fun coin created 13 minutes ago by DcuQ…jjDv. Token-2022, mint
       and freeze authority revoked, metadata immutable. Still on the bonding
       curve, so there is no LP token. No Artist Passport record (devnet).
       Holder list not checked: needs a private RPC. Looked up 21:43 UTC.
```

## Install

As a plugin (recommended):

```
/plugin marketplace add KevinGod1234/solana-token-intel
/plugin install solana-token-intel@solana-token-intel
```

Or from a clone, as a personal skill:

```
git clone https://github.com/KevinGod1234/solana-token-intel
cd solana-token-intel
python3 install.py
```

Python 3.8 or newer. Nothing else to install: standard library only.

## Keys (optional)

Everything works without keys. Keys make answers more complete.

| Variable | Adds | Without it |
| --- | --- | --- |
| `SOLANA_RPC_URL` | Holder lists, LP holders, faster lookups | Public RPC: slow; holder lists do not work |
| `HELIUS_API_KEY` | Full history for origin lookups | Origin pages back up to 10,000 signatures |
| `BIRDEYE_API_KEY` | Price across all pools | GeckoTerminal, most liquid pool only |
| `PASSPORT_RPC_URL` | Artist Passport on another cluster | Devnet |

Add them with the setup screen. Input is hidden and the file is readable only
by you (`~/.config/solana-token-intel/.env`):

```
python3 skills/solana-token-intel/scripts/cli.py setup     # from a clone
python3 ~/.claude/skills/solana-token-intel/scripts/cli.py setup
```

Then check every source:

```
python3 .../scripts/cli.py doctor
```

Environment variables with the same names win over the file. Never paste a
key into a Claude conversation; the skill will refuse it.

## Run the scripts yourself

Each script prints one JSON object. Add `--pretty` for a readable view.

```
python3 skills/solana-token-intel/scripts/risk.py <mint> --pretty
```

| Script | Answers |
| --- | --- |
| `overview.py` | Supply, decimals, authorities, Token-2022 extensions, name and metadata |
| `origin.py` | Creation time, creator wallet, launchpad, creator's prior activity |
| `history.py` | Price and volume candles (`--interval 1m…1d`, `--limit ≤1000`) |
| `pools.py` | Pools, liquidity, LP burned or held |
| `holders.py` | Largest holders, program accounts labelled, holder count |
| `risk.py` | Risk signals with evidence (runs the four above) |
| `endorsement.py` | Artist Passport endorsements and disavowals |

What each field means: `skills/solana-token-intel/references/reading-results.md`.
Data sources, limits and terms: `docs/sources.md`.

## Develop

```
python3 -m unittest discover tests   # offline, saved responses
python3 tests/live.py                # every script against tests/tokens.md
```

The terminal colors live in one place, `PALETTE` in `scripts/common.py`.
`NO_COLOR=1` turns them off.

## License

MIT
