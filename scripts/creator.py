#!/usr/bin/env python3
"""The creator's track record: their other coins and how each stands now,
and what the creator did with this coin after making it, next to its peak."""

import re
import time
from argparse import Namespace

import history
import origin
import outcomes
from common import DEXSCREENER_API, HELIUS_API, SourceError, config, from_iso, http_json, iso, rpc, rpc_url, script
from risk import run

WSOL = "So11111111111111111111111111111111111111112"
MAX_COINS = 30         # DEX Screener takes 30 mints per call
CREATE_PAGES = 5       # Helius search windows for CREATE transactions
ACTIVITY_PAGES = 3     # pages of 100 creator transactions after creation


def created_mint(tx):
    """The new token in a Helius CREATE transaction."""
    transfers = tx.get("tokenTransfers") or []
    # The creator's own first buy names the new coin; other mints can be route tokens.
    mints = [t["mint"] for t in transfers if t.get("toUserAccount") == tx.get("feePayer")]
    mints += [t["mint"] for t in transfers]
    mints += [c["mint"] for a in tx.get("accountData") or [] for c in a.get("tokenBalanceChanges") or []]
    return next((m for m in mints if m and m != WSOL), None)


def creator_coins(creator, key, result):
    """Coins this wallet created, newest first, from Helius CREATE transactions."""
    coins, before = [], None
    for _ in range(CREATE_PAGES):
        # A type filter searches one window of history at a time: a short page is not the end, and an
        # empty window is a 404 that names the signature to continue from.
        try:
            page = http_json(f"{HELIUS_API}/addresses/{creator}/transactions?api-key={key}&limit=100&type=CREATE"
                             + (f"&before-signature={before}" if before else ""))
        except SourceError as e:
            hint = re.search(r"before-signature` parameter set to ([1-9A-HJ-NP-Za-km-z]{64,90})", e.body)
            if e.status != 404 or not hint:
                raise
            before = hint.group(1)
            continue
        if not page:
            break
        coins += [{"mint": created_mint(t), "created_at": iso(t.get("timestamp")), "helius_source": t.get("source")}
                  for t in page if not t.get("transactionError")]
        before = page[-1]["signature"]
    else:
        result.miss("older coins by this creator", f"searched {CREATE_PAGES} Helius history windows without reaching "
                    "the wallet's first transaction; older coins are not included", partial=False)
    # shortcut: relies on Helius typing the creation as CREATE (seen for pump.fun); other launchpads may be missed, check them when tests/tokens.md gains one.
    oldest = {c["mint"]: c for c in coins if c["mint"]}  # newest first, so the oldest entry wins; a lock can repeat a mint
    return list(oldest.values())


def coin_states(coins, result):
    """Most liquid DEX Screener pair per coin: price, liquidity, market cap now.
    Also returns {mint: set of pool addresses}."""
    if not coins:
        return [], {}
    if len(coins) > MAX_COINS:
        result.miss(f"price and liquidity of {len(coins) - MAX_COINS} older coins by this creator",
                    f"only the {MAX_COINS} newest are checked", partial=False)
        coins = coins[:MAX_COINS]
    pairs = http_json(f"{DEXSCREENER_API}/tokens/v1/solana/{','.join(c['mint'] for c in coins)}") or []
    result.source("DEX Screener", DEXSCREENER_API)
    best, pools = {}, {}
    for p in pairs:
        liq = lambda q: (q.get("liquidity") or {}).get("usd") or 0
        mint = p["baseToken"]["address"]
        pools.setdefault(mint, set()).add(p["pairAddress"])
        if mint not in best or liq(p) > liq(best[mint]):
            best[mint] = p
    rows = []
    for c in coins:
        p = best.get(c["mint"]) or {}
        rows.append({"mint": c["mint"], "symbol": (p.get("baseToken") or {}).get("symbol"),
                     "status": "trading" if p else "no pools listed",
                     "liquidity_usd": (p.get("liquidity") or {}).get("usd"), "market_cap_usd": p.get("marketCap"),
                     "price_usd": float(p["priceUsd"]) if p.get("priceUsd") else None,
                     "created_at": c["created_at"], "name": (p.get("baseToken") or {}).get("name"),
                     "helius_source": c["helius_source"]})
    return rows, pools


def move_kind(out, tx_type, counterparty, pools):
    if not out:
        return "received"
    if tx_type == "SWAP":
        return "sold"
    return "sent to pool" if counterparty in pools else "sent"


def creator_moves(mint, creator, created_ts, pools, key, result):
    """This coin going in and out of the creator wallet, oldest first, from creation on."""
    moves, after, done, checked_to = [], created_ts - 1, False, None
    for _ in range(ACTIVITY_PAGES):
        page = http_json(f"{HELIUS_API}/addresses/{creator}/transactions?api-key={key}&limit=100"
                         f"&sort-order=asc&gt-time={after}")
        for tx in page:
            for t in tx.get("tokenTransfers") or []:
                if t.get("mint") != mint or creator not in (t.get("fromUserAccount"), t.get("toUserAccount")):
                    continue
                out = t["fromUserAccount"] == creator
                other = t["toUserAccount"] if out else t["fromUserAccount"]
                moves.append({"time": iso(tx["timestamp"]), "kind": move_kind(out, tx.get("type"), other, pools),
                              "amount": t.get("tokenAmount"), "counterparty": other, "signature": tx["signature"]})
        checked_to = iso(page[-1]["timestamp"]) if page else checked_to
        if len(page) < 100:
            done = True
            break
        after = page[-1]["timestamp"]  # shortcut: transactions sharing that second are skipped, fine for a wallet's pace.
    if not done:
        result.miss("later creator activity", f"checked the creator's first {ACTIVITY_PAGES * 100} transactions after "
                    "creation only; later sells or transfers are not included", partial=False)
    return moves, done, checked_to


def collect(mint, result, args):
    od = run(origin, mint, Namespace(max_pages=args.max_pages), result)
    creator = od.get("creator")
    if not creator:
        result.miss("creator track record", "the creator could not be found (see the origin entries above)")
        result["data"] = {"creator": None}
        return
    data = {"creator": creator, "created_at": od.get("created_at"), "launchpad": od.get("launchpad")}
    key = config()["HELIUS_API_KEY"]

    # Peak of this coin: hourly candles reach about 41 days back, daily ones further.
    age_days = (time.time() - origin_ts(od)) / 86400
    hd = run(history, mint, Namespace(interval="1h" if age_days < 41 else "1d", limit=1000), result)
    peak = max(hd.get("candles") or [], key=lambda c: c["high"] or 0, default=None)
    data["this_coin"] = {"peak_price_usd": peak["high"] if peak else None, "peak_at": peak["time"] if peak else None,
                         "peak_covers_full_history": hd.get("covers_full_history"),
                         "price_usd": hd.get("price_usd")}

    result.source("Solana RPC", rpc_url())
    try:
        held = rpc("getTokenAccountsByOwner", [creator, {"mint": mint}, {"encoding": "jsonParsed"}])["value"]
        data["this_coin"]["creator_holds_now"] = sum(
            a["account"]["data"]["parsed"]["info"]["tokenAmount"]["uiAmount"] or 0 for a in held)
    except SourceError as e:
        result.miss("creator's current balance", str(e))

    if not key:
        for what in ("other coins by this creator", "creator sells of this coin"):
            result.miss(what, "HELIUS_API_KEY is not set; the creator's parsed history needs it (/mint:setup)")
        result["data"] = data
        return
    result.source("Helius", HELIUS_API)
    pools = {}
    try:
        coins = creator_coins(creator, key, result)
        if mint not in (c["mint"] for c in coins):  # origin found it even if the CREATE list did not
            coins.append({"mint": mint, "created_at": od.get("created_at"), "helius_source": None})
        coins.sort(key=lambda c: c["created_at"] or "", reverse=True)
        found = len(coins)
        coins, pools = coin_states(coins, result)
        for c in coins:
            c["is_this_coin"] = c["mint"] == mint
        data.update(coins_found=found, coins_priced=len(coins), coins_without_pools=sum(c["status"] != "trading" for c in coins),
                    coins=coins)
    except SourceError as e:
        result.miss("other coins by this creator", str(e))
    try:
        moves, complete, checked_to = creator_moves(mint, creator, origin_ts(od), pools.get(mint, set()), key, result)
        total = lambda kind: round(sum(m["amount"] or 0 for m in moves if m["kind"] == kind), 6)
        if peak:
            peak_ts = from_iso(peak["time"])
            for m in moves:
                m["hours_from_peak"] = round((from_iso(m["time"]) - peak_ts) / 3600, 2)
        data["this_coin"].update(creator_received=total("received"), creator_sold=total("sold"),
                                 creator_sent_to_pool=total("sent to pool"), creator_sent=total("sent"),
                                 activity_complete=complete, activity_checked_to=checked_to, creator_moves=moves)
    except SourceError as e:
        result.miss("creator sells of this coin", str(e))
    result["data"] = data
    outcomes.save_sample(mint, od.get("created_at"))


def origin_ts(od):
    return from_iso(od["created_at"]) if od.get("created_at") else time.time()


def add_args(parser):
    parser.add_argument("--max-pages", type=int, default=10, help="origin lookup depth without Helius (default 10)")


if __name__ == "__main__":
    script(__doc__, collect, add_args)
