#!/usr/bin/env python3
"""Largest holders and their share of supply, with program accounts
(pools, vaults, bonding curves) labelled so they are not mistaken for people."""

from common import (GECKO_API, PUBLIC_RPC, SYSTEM_PROGRAM, SourceError, accounts, b58decode,
                    http_json, known_programs, on_curve, rpc, rpc_url, script)


def label_owners(owners):
    """{owner: {kind, program}} from each owner's own account and its curve point."""
    known = known_programs()
    info = accounts(owners)
    out = {}
    for owner in owners:
        acc = info.get(owner)
        program = acc["owner"] if acc else None
        is_program = (acc is not None and acc.get("executable")) or not on_curve(b58decode(owner)) \
            or (program not in (None, SYSTEM_PROGRAM))
        out[owner] = {
            "kind": "program account" if is_program else "wallet",
            "program": known.get(program, {}).get("name") or (program if is_program else None),
        }
    return out


def collect(mint, result, args=None):
    url = rpc_url()
    data = {}
    try:
        info = http_json(f"{GECKO_API}/networks/solana/tokens/{mint}/info")["data"]["attributes"]
        result.source("GeckoTerminal", GECKO_API)
        holders = info.get("holders") or {}
        if holders.get("count") is not None:
            data["holder_count"] = holders["count"]
            data["distribution_pct"] = {k: float(v) for k, v in
                                        (holders.get("distribution_percentage") or {}).items()}
            data["distribution_updated_at"] = holders.get("last_updated")
        else:
            result.miss("holder count", "GeckoTerminal has not indexed holders for this token yet", partial=False)
    except (SourceError, KeyError, TypeError) as e:
        result.miss("holder count", f"GeckoTerminal token info: {e}", partial=False)

    result.source("Solana RPC", url)
    try:
        # The public RPC refuses this method (checked 2026-10-14), so try it once there.
        largest = rpc("getTokenLargestAccounts", [mint], retries=0 if url == PUBLIC_RPC else 4)["value"]
        supply = rpc("getTokenSupply", [mint])["value"]
    except SourceError as e:
        result.miss("largest holders by wallet", str(e))
        result["data"] = data
        return
    total = int(supply["amount"])
    parsed = accounts([a["address"] for a in largest], encoding="jsonParsed")
    owner_of = {addr: (acc or {}).get("data", {}).get("parsed", {}).get("info", {}).get("owner")
                for addr, acc in parsed.items()}
    labels = label_owners([o for o in owner_of.values() if o])

    holders = []
    for rank, a in enumerate(largest, 1):
        owner = owner_of.get(a["address"])
        label = labels.get(owner, {"kind": "unknown", "program": None})
        holders.append({
            "rank": rank,
            "owner": owner,
            "share_pct": round(int(a["amount"]) / total * 100, 4) if total else None,
            "amount": a["uiAmountString"],
            "owner_kind": label["kind"],
            "program": label["program"],
            "token_account": a["address"],
        })
    people = [h for h in holders if h["owner_kind"] == "wallet"]
    share = lambda rows: round(sum(h["share_pct"] or 0 for h in rows), 4)
    data.update({
        "supply": supply["uiAmountString"],
        "summary": {
            "top10_share_pct": share(holders[:10]),
            "top10_wallets_share_pct": share(people[:10]),
            "largest_wallet_share_pct": people[0]["share_pct"] if people else None,
            "program_accounts_in_top": sum(h["owner_kind"] == "program account" for h in holders),
        },
        "holders": holders,
    })
    result["data"] = data


if __name__ == "__main__":
    script(__doc__, collect)
