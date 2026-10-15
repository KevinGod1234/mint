---
description: What happened to coins like this one at 1, 7 and 30 days, with sample sizes.
argument-hint: <mint address>
allowed-tools: Bash(mint *)
disable-model-invocation: true
---

Run `mint outcomes <mint>` for the address in "$ARGUMENTS". Read the
`outcomes` section of `${CLAUDE_PLUGIN_ROOT}/references/reading-results.md` first.

Give the user's own rates (`yours`) as "of N coins you looked up, checked at
7 days, M had a transaction in the 24 hours before the check". Say how small
N is when it is small, and that the sample holds only coins they chose to
check. Then give this coin's own facts (`this_coin`).

These numbers are history, not a forecast. Never say "this coin will" or give
odds for this coin. Follow the wording rules of the `check` skill. If the user
asks where their samples are kept, give `yours.file`: it stays on their
computer and is never uploaded.
