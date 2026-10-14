---
description: Largest holders of a Solana token and their share of supply.
argument-hint: <mint address>
allowed-tools: Bash(mint *)
disable-model-invocation: true
---

Run `mint holders <mint>` for the address in "$ARGUMENTS". List the largest
holders with their share, and keep program accounts (pools, vaults, bonding
curves) apart from wallets. Give the holder count and top-10 share when
present.

If the list is missing because the public RPC refused it, say so and point to
`/mint:setup` for adding a private RPC. Follow the wording rules of the
`check` skill: concentration is a fact, not a verdict.
