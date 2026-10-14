# Known programs

The scripts read this table at run time. `origin.py` uses it to name the
launchpad that created a token, and `holders.py` and `pools.py` use it to label
program accounts. Add a row to teach them a new program. The Kind column is
one of `launchpad`, `amm`, `token` or `system`.

Every ID below was checked on 2026-10-14: `getMultipleAccounts` on mainnet
returned an executable account owned by a BPF loader. A program being live
does not prove who runs it. The last column names where each project
publishes its ID; those pages were not re-read for this check, so re-check
them before relying on a new row.

| Name | Kind | Program ID | Docs |
| --- | --- | --- | --- |
| pump.fun | launchpad | `6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P` | github.com/pump-fun/pump-public-docs |
| Raydium LaunchLab (incl. letsbonk.fun) | launchpad | `LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj` | docs.raydium.io, program addresses |
| Meteora Dynamic Bonding Curve | launchpad | `dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN` | docs.meteora.ag, program IDs |
| Moonshot | launchpad | `MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG` | docs.moonshot.money |
| PumpSwap | amm | `pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA` | github.com/pump-fun/pump-public-docs |
| Raydium AMM v4 | amm | `675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8` | docs.raydium.io, program addresses |
| Raydium CPMM | amm | `CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C` | docs.raydium.io, program addresses |
| Raydium CLMM | amm | `CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK` | docs.raydium.io, program addresses |
| Orca Whirlpools | amm | `whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc` | dev.orca.so |
| Meteora DLMM | amm | `LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo` | docs.meteora.ag, program IDs |
| Meteora DAMM v1 | amm | `Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB` | docs.meteora.ag, program IDs |
| Meteora DAMM v2 | amm | `cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG` | docs.meteora.ag, program IDs |
| SPL Token | token | `TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA` | spl.solana.com |
| Token-2022 | token | `TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb` | spl.solana.com |
| Metaplex Token Metadata | token | `metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s` | developers.metaplex.com |
| Associated Token Account | token | `ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL` | spl.solana.com |
| System Program | system | `11111111111111111111111111111111` | solana.com/docs |
| Compute Budget | system | `ComputeBudget111111111111111111111111111111` | solana.com/docs |

## LP token location

`pools.py` reads the LP mint from the pool account at these byte offsets.
Each offset was checked on 2026-10-14 against a live pool: the 32 bytes at
the offset decoded to an existing token mint.

| Program | Offset | Pool used to check |
| --- | --- | --- |
| Raydium AMM v4 | 464 | `58oQChx4yWmvKdwLLZzBi4ChoCc2fqCUWBkwMihLYQo2` (SOL/USDC) |
| Raydium CPMM | 136 | `DywR4cjNLhPy1dV9tBShpCbXoAAq3LN3Wajj9Gw64co9` (LIBRA) |
| Meteora DAMM v1 | 8 | `CeubWwtcmVctX47UWLmVZJ9zENtC5tdBecfE6sb4gU7k` (LIBRA) |
| PumpSwap | 107 | `AnrCHvfJUzMtos8DGjpT2XKurVPPYAVLDturASNwXcd4` (CRAWLER) |

Concentrated-liquidity pools (Raydium CLMM, Orca Whirlpools, Meteora DLMM,
Meteora DAMM v2) hold liquidity in position NFTs, not an LP token, so "LP
burned" does not apply to them.
