#!/usr/bin/env python3
"""Pools for a token: program, liquidity, and where the LP tokens are
(burned, held by a wallet, or not applicable)."""

from common import (BURN_ADDRESS, DEXSCREENER_API, PUBLIC_RPC, SourceError, account_bytes,
                    accounts, b58encode, http_json, iso, known_programs, rpc, rpc_url, script)

# Byte offset of the LP mint inside each pool account (see references/launchpads.md).
LP_MINT_OFFSET = {
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": 464,  # Raydium AMM v4
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": 136,  # Raydium CPMM
    "Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB": 8,    # Meteora DAMM v1
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": 107,   # PumpSwap
}
POSITION_BASED = {
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK",  # Raydium CLMM
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc",   # Orca Whirlpools
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo",   # Meteora DLMM
    "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG",   # Meteora DAMM v2
}
MAX_POOLS = 20


def lp_model(program, known):
    if program in LP_MINT_OFFSET:
        return "LP token"
    if program in POSITION_BASED:
        return "positions"
    if known.get(program, {}).get("kind") == "launchpad":
        return "bonding curve"
    return "unknown"


def lp_holders(row, lp_mint, supply, url):
    """Who holds the LP tokens: burn address share and the largest holder."""
    largest = rpc("getTokenLargestAccounts", [lp_mint], retries=0 if url == PUBLIC_RPC else 4)["value"]
    owners = accounts([a["address"] for a in largest], encoding="jsonParsed")
    owner = lambda a: ((owners.get(a["address"]) or {}).get("data", {}).get("parsed", {})
                       .get("info", {}).get("owner"))
    pct = lambda amount: round(int(amount) / supply * 100, 4)
    row["lp_at_burn_address_pct"] = round(sum(pct(a["amount"]) for a in largest if owner(a) == BURN_ADDRESS), 4)
    if largest:
        row["largest_lp_holder_pct"] = pct(largest[0]["amount"])
        row["largest_lp_holder"] = owner(largest[0])


def collect(mint, result, args=None):
    url = rpc_url()
    known = known_programs()
    pairs = http_json(f"{DEXSCREENER_API}/token-pairs/v1/solana/{mint}") or []
    result.source("DEX Screener", DEXSCREENER_API)
    pairs.sort(key=lambda p: (p.get("liquidity") or {}).get("usd") or 0, reverse=True)
    if len(pairs) > MAX_POOLS:
        result.miss(f"{len(pairs) - MAX_POOLS} smaller pools", f"only the {MAX_POOLS} most liquid are checked", partial=False)
        pairs = pairs[:MAX_POOLS]

    pool_accounts = accounts([p["pairAddress"] for p in pairs]) if pairs else {}
    result.source("Solana RPC", url)
    rows = []
    for p in pairs:
        acc = pool_accounts.get(p["pairAddress"])
        program = acc["owner"] if acc else None
        row = {
            "dex": p.get("dexId"),
            "pair": f"{p['baseToken']['symbol']}/{p['quoteToken']['symbol']}",
            "liquidity_usd": (p.get("liquidity") or {}).get("usd"),
            "lp_model": lp_model(program, known),
            "lp_note": None,
            "lp_at_burn_address_pct": None,
            "largest_lp_holder_pct": None,
            "pool": p["pairAddress"],
            "program": known.get(program, {}).get("name") or program,
            "created_at": iso(p["pairCreatedAt"] / 1000) if p.get("pairCreatedAt") else None,
        }
        if program in LP_MINT_OFFSET:
            raw = account_bytes(acc)
            row["lp_mint"] = b58encode(raw[LP_MINT_OFFSET[program]:LP_MINT_OFFSET[program] + 32])
        rows.append(row)

    lp_rows = [r for r in rows if r.get("lp_mint")]
    lp_mints = accounts([r["lp_mint"] for r in lp_rows], encoding="jsonParsed") if lp_rows else {}
    holder_error = None
    for row in lp_rows:
        parsed = ((lp_mints.get(row["lp_mint"]) or {}).get("data") or {}).get("parsed") or {}
        if parsed.get("type") != "mint":
            result.miss(f"LP token for pool {row['pool']}", "the LP mint read from the pool is not a token mint")
            row["lp_mint"] = None
            continue
        supply = int(parsed["info"]["supply"])
        row["lp_supply_raw"] = supply
        if supply == 0:
            row["lp_note"] = "all burned (supply 0)"
        elif not holder_error:
            try:
                lp_holders(row, row["lp_mint"], supply, url)
            except SourceError as e:
                holder_error = str(e)
    if holder_error:
        result.miss("who holds the LP tokens", holder_error)

    top = pairs[0] if pairs else {}
    result["data"] = {
        "pool_count": len(rows),
        "total_liquidity_usd": round(sum(r["liquidity_usd"] or 0 for r in rows), 2),
        "price_usd": float(top["priceUsd"]) if top.get("priceUsd") else None,
        "fdv_usd": top.get("fdv"),
        "market_cap_usd": top.get("marketCap"),
        "pools": rows,
    }
    if not rows:
        result.miss("pools", "DEX Screener lists no pools for this token", partial=False)
    if lp_rows:
        result.miss("LP burned with the Burn instruction",
                    "burning lowers LP supply; without the starting supply the burned share cannot be measured",
                    partial=False)


if __name__ == "__main__":
    script(__doc__, collect)
