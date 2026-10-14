# Test tokens

Run every script against these before a release:

```
python3 tests/live.py
```

`tests/live.py` reads the table below. Picked and checked on 2026-10-14.
New pump.fun coins age fast: replace that row with a coin from the last hour
before each release (GeckoTerminal `/networks/solana/new_pools`).

| Kind | Name | Mint | Why it is here |
| --- | --- | --- | --- |
| new | CyberAxe (pump.fun, Token-2022) | `A1cNG1fuMuJjwmEKEwMyeVQcxgkk2GyjuBns9znUpump` | Fresh bonding-curve coin, short history |
| graduated | CRAWLER (pump.fun to PumpSwap) | `CQCDTp8rsFV3PhaPeYjcCW5LdGTxi6jFx7eC3UXnpump` | Graduated; PumpSwap LP fully burned |
| well-known | USDC | `EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v` | Live mint and freeze authority on purpose; huge history |
| well-known | BONK | `DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263` | Large community token, many pools |
| well-known | JUP | `JUPyiwrYJFskUPiHa7hkeR8VUtAeFoSYbKedZNsDvCN` | Large token, Metaplex metadata |
| well-known | PYUSD (Token-2022) | `2b1kV6DkPAnxd5ixfnxCpjxmKwqjjaYmCZfHsFu24GXo` | Many Token-2022 extensions |
| known rug | LIBRA | `Bo9jh3wsmcC2AjakLWzNmKJ3SgtZmXEcSaW7L2FAvUsU` | Widely reported collapse, Feb 2025; liquidity pulled |
| endorsed (devnet) | riff demo coin | `DffTqQTB8YsqFMA5gewV7NPau3NRxHj8AsqAGR77UWGt` | Artist Passport record: endorsed |
| disavowed (devnet) | riff demo coin | `98EFoVUTSeTdNBXmPSmb7SPuDeyXnsZSwFrR17J5PAMU` | Artist Passport record: disavowed |

The two devnet mints exist only on devnet: mainnet scripts are expected to
fail on them, so `live.py` runs only `endorsement.py` for them.
