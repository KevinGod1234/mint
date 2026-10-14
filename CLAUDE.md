# solana-token-intel

Open-source Claude Code skill with scripts that look up a Solana token's
make-up, origin, price history, pools, holders, risk signals and Artist
Passport endorsements. Users bring their own RPC URL and API keys. See PLAN.md.

## Ground rules

- **Read-only.** No script signs, sends or simulates a transaction, or touches
  a wallet or private key.
- **Keys never leave the environment.** Read them from environment variables
  or a git-ignored `.env`. Never print, log or return a key, and never put one
  in an error message or a returned URL. Never ask a user to paste a key into
  the conversation.
- **Facts, not advice.** Outputs and SKILL.md wording never say buy, sell,
  safe, or predict prices. A risk signal is evidence, not a verdict.
- **Say what is missing.** Every result lists its sources and anything that
  could not be checked.

## Code

- Plugin layout: the skill lives in `skills/solana-token-intel/` (SKILL.md,
  `scripts/`, `references/`); the repo root holds `.claude-plugin/`, docs and
  tests. Paths below are relative to the skill folder.
- Everything a person sees in a terminal (setup, doctor, `--pretty`, tests)
  uses the helpers and `PALETTE` in `scripts/common.py`. Do not add colors or
  layouts elsewhere.
- Python 3, standard library only (urllib, json). No dependencies to install.
- One script per question; each prints exactly one JSON object to stdout.
  Errors go to stderr as JSON with a plain message.
- Shared code lives in `scripts/common.py`: config, HTTP with retries and
  backoff, JSON output, key redaction.
- Respect rate limits: back off on 429, cap retries, and say so in the output
  when data is partial.
- Free sources must work without any key. Keys only improve completeness.

## Data sources

- Before using a source, check its current endpoints, limits and terms of use,
  and record them with the date in `docs/sources.md`.
- Launchpad detection uses program IDs listed in
  `references/launchpads.md`, each with where it was verified.
- Artist Passport lookups use the passport program's published IDL
  (github.com/use-riff/riff, `idl/riff_passport.json`). Devnet until the
  program is on mainnet.

## Testing

- Keep a fixed list of test tokens in `tests/tokens.md` (new, graduated,
  well-known, known rug) and run every script against them before a release.
- Unit tests for parsing use saved JSON responses in `tests/fixtures/`, with any
  keys removed.

## Style

- SKILL.md stays short: when to use it, which script answers what, wording
  rules. Details go in references/.
- Plain English, short sentences.
