#!/usr/bin/env python3
"""Price and volume candles over time. Uses Birdeye (all pools) when
BIRDEYE_API_KEY is set, else GeckoTerminal (the most liquid pool)."""

import time

from common import BIRDEYE_API, GECKO_API, SourceError, config, http_json, iso, script

INTERVALS = {  # name: (seconds, GeckoTerminal timeframe, aggregate, Birdeye type)
    "1m": (60, "minute", 1, "1m"),
    "5m": (300, "minute", 5, "5m"),
    "15m": (900, "minute", 15, "15m"),
    "1h": (3600, "hour", 1, "1H"),
    "4h": (14400, "hour", 4, "4H"),
    "12h": (43200, "hour", 12, "12H"),
    "1d": (86400, "day", 1, "1D"),
}


def candle(ts, o, h, l, c, v):
    return {"time": iso(ts), "open": o, "high": h, "low": l, "close": c, "volume": v}


def from_birdeye(mint, interval, limit, key):
    seconds, _, _, kind = INTERVALS[interval]
    end = int(time.time())
    reply = http_json(f"{BIRDEYE_API}/defi/ohlcv?address={mint}&type={kind}"
                      f"&time_from={end - seconds * limit}&time_to={end}",
                      headers={"X-API-KEY": key, "x-chain": "solana"})
    items = (reply.get("data") or {}).get("items") or []
    return [candle(i["unixTime"], i["o"], i["h"], i["l"], i["c"], i["v"]) for i in items]


def top_pool(mint):
    # GeckoTerminal ranks pools itself; re-sorting by reserve picks mispriced dead pools.
    pools = http_json(f"{GECKO_API}/networks/solana/tokens/{mint}/pools?page=1")["data"]
    return pools[0] if pools else None


def from_gecko(pool, mint, interval, limit):
    _, frame, aggregate, _ = INTERVALS[interval]
    reply = http_json(f"{GECKO_API}/networks/solana/pools/{pool}/ohlcv/{frame}"
                      f"?aggregate={aggregate}&limit={limit}&currency=usd&token={mint}")
    rows = reply["data"]["attributes"]["ohlcv_list"]
    return [candle(*row) for row in reversed(rows)]  # GeckoTerminal sends newest first


def collect(mint, result, args):
    interval, limit = args.interval, max(1, min(args.limit, 1000))
    data = {"interval": interval}
    candles = None
    key = config()["BIRDEYE_API_KEY"]
    if key:
        try:
            candles = from_birdeye(mint, interval, limit, key)
            result.source("Birdeye", BIRDEYE_API)
            data.update(scope="token, all pools", volume_unit="as reported by Birdeye (not verified)")
        except (SourceError, KeyError, TypeError) as e:
            result.miss("Birdeye price history", f"{e}; fell back to GeckoTerminal", partial=False)
    else:
        result.miss("price across all pools", "BIRDEYE_API_KEY is not set; showing the most liquid pool only",
                    partial=False)

    pool = top_pool(mint)
    result.source("GeckoTerminal", GECKO_API)
    if pool:
        attrs = pool["attributes"]
        data.update(pool=attrs["address"], pool_name=attrs.get("name"), pool_created_at=attrs.get("pool_created_at"),
                    price_usd=float(attrs["token_price_usd"]) if attrs.get("token_price_usd") else None,
                    fdv_usd=float(attrs["fdv_usd"]) if attrs.get("fdv_usd") else None,
                    market_cap_usd=float(attrs["market_cap_usd"]) if attrs.get("market_cap_usd") else None)
        if candles is None:
            candles = from_gecko(attrs["address"], mint, interval, limit)
            data.update(scope="most liquid pool", volume_unit="usd")
    if not candles:
        result.miss("candles", "no trades found for this token in the chosen range")
        candles = []
    closes = [c["close"] for c in candles if c["close"]]
    data.update(
        first_candle=candles[0]["time"] if candles else None,
        last_candle=candles[-1]["time"] if candles else None,
        change_pct=round((closes[-1] / closes[0] - 1) * 100, 2) if len(closes) > 1 else None,
        high=max((c["high"] for c in candles), default=None),
        low=min((c["low"] for c in candles), default=None),
        candles=candles,
    )
    result["data"] = data
    result.miss("market cap over time", "sources give candles for price only; current market cap is shown",
                partial=False)


def add_args(parser):
    parser.add_argument("--interval", choices=INTERVALS, default="1h", help="candle size (default 1h)")
    parser.add_argument("--limit", type=int, default=168, help="number of candles, max 1000 (default 168)")


if __name__ == "__main__":
    script(__doc__, collect, add_args)
