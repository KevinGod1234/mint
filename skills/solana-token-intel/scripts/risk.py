#!/usr/bin/env python3
"""Risk signals with the evidence behind each. Runs overview, origin, holders
and pools. A signal is evidence, not a verdict."""

from argparse import Namespace
from datetime import datetime

import holders
import origin
import overview
import pools
from common import Result, SourceError, script

TOP10_WALLETS_PCT = 30
NEW_WALLET_HOURS = 24
LP_BURNED_PCT = 90
EXTENSION_EFFECTS = {
    "PermanentDelegate": "a delegate can transfer or burn tokens from any account",
    "TransferHook": "a custom program runs on every transfer",
    "TransferFeeConfig": "transfers can carry a fee",
    "NonTransferable": "tokens cannot be transferred",
    "DefaultAccountState": "new token accounts can start frozen",
    "MintCloseAuthority": "the mint account can be closed",
    "Pausable": "transfers can be paused",
}


def signal(sid, label, status, evidence, threshold=None):
    return {"signal": sid, "status": status, "label": label, "evidence": evidence,
            **({"threshold": threshold} if threshold else {})}


def run(part, mint, args, result):
    sub = Result(part.__name__, mint)
    try:
        part.collect(mint, sub, args)
    except SourceError as e:
        sub.miss(f"{part.__name__} lookup", str(e))
    except (KeyError, TypeError, IndexError) as e:
        sub.miss(f"{part.__name__} lookup", f"unexpected response shape ({type(e).__name__}: {e})")
    result.merge(sub)
    return sub["data"]


def authority_signals(ov):
    out = []
    for key, sid, label in (("mint_authority", "mint_authority_live", "More tokens can be minted"),
                            ("freeze_authority", "freeze_authority_live", "Token accounts can be frozen")):
        value = ov.get(key)
        out.append(signal(sid, label, "found" if value else "not found",
                          f"{key.replace('_', ' ')}: {value}" if value else f"{key.replace('_', ' ')} is revoked"))
    return out


def extension_signal(ov):
    if ov.get("token_program") != "Token-2022":
        return signal("token2022_extensions", "Token-2022 extensions that limit holders", "not applicable",
                      "SPL Token mint: no extensions")
    risky = []
    for ext in ov.get("extensions", []):
        if ext["name"] not in EXTENSION_EFFECTS:
            continue
        if ext["name"] == "DefaultAccountState" and ext.get("default_state") != "frozen":
            continue
        if ext["name"] == "TransferHook" and not ext.get("hook_program") and not ext.get("authority"):
            continue
        detail = ", ".join(f"{k} {v}" for k, v in ext.items() if k != "name")
        risky.append(f"{ext['name']} ({EXTENSION_EFFECTS[ext['name']]}{'; ' + detail if detail else ''})")
    return signal("token2022_extensions", "Token-2022 extensions that limit holders",
                  "found" if risky else "not found", "; ".join(risky) or "none of the listed extensions",
                  threshold="any of: " + ", ".join(EXTENSION_EFFECTS))


def metadata_signal(ov):
    meta = ov.get("metadata")
    if not meta:
        return signal("metadata_editable", "Name, symbol or image can be changed", "not checked", "no metadata found")
    editable = meta.get("is_mutable") and meta.get("update_authority")
    return signal("metadata_editable", "Name, symbol or image can be changed", "found" if editable else "not found",
                  f"update authority {meta['update_authority']} ({meta['source']})" if editable
                  else f"metadata is immutable ({meta['source']})")


def holder_signal(hd):
    summary = hd.get("summary")
    threshold = f"top 10 wallets hold {TOP10_WALLETS_PCT}% or more (program accounts excluded)"
    if not summary:
        top10 = (hd.get("distribution_pct") or {}).get("top_10")
        evidence = (f"wallet-level holders unavailable; GeckoTerminal says the top 10 accounts, pools included, "
                    f"hold {top10}%" if top10 is not None else "holder list unavailable")
        return signal("holder_concentration", "Supply is concentrated in few wallets", "not checked", evidence, threshold)
    share = summary["top10_wallets_share_pct"]
    return signal("holder_concentration", "Supply is concentrated in few wallets",
                  "found" if share >= TOP10_WALLETS_PCT else "not found",
                  f"top 10 wallets hold {share}%; largest wallet {summary['largest_wallet_share_pct']}%; "
                  f"{summary['program_accounts_in_top']} program accounts in the top 20 were excluded", threshold)


def liquidity_signal(pd):
    label = "Liquidity can be withdrawn by an LP holder"
    threshold = f"in the most liquid pool, less than {LP_BURNED_PCT}% of LP tokens are burned"
    rows = pd.get("pools") or []
    if not rows:
        return signal("liquidity_unlocked", label, "not checked", "no pools found", threshold)
    top = rows[0]
    where = f"{top['dex']} {top['pair']} ({top['pool']})"
    if top["lp_model"] != "LP token":
        return signal("liquidity_unlocked", label, "not applicable",
                      f"most liquid pool {where} uses {top['lp_model']}, not an LP token", threshold)
    if top.get("lp_note"):
        return signal("liquidity_unlocked", label, "not found", f"{where}: {top['lp_note']}", threshold)
    burned = top.get("lp_at_burn_address_pct")
    if burned is None:
        return signal("liquidity_unlocked", label, "not checked", f"{where}: LP holders could not be read", threshold)
    holder = f"; largest LP holder {top.get('largest_lp_holder')} has {top.get('largest_lp_holder_pct')}%"
    return signal("liquidity_unlocked", label, "found" if burned < LP_BURNED_PCT else "not found",
                  f"{where}: {burned}% of LP tokens at the burn address{holder}", threshold)


def creator_signal(od):
    label = "Creator wallet was new when the token was made"
    threshold = f"creator first seen less than {NEW_WALLET_HOURS} hours before creation"
    if not od.get("created_at"):
        return signal("new_creator_wallet", label, "not checked", "creation transaction not found", threshold)
    if "creator_prior_tx_count" not in od:
        return signal("new_creator_wallet", label, "not checked", "creator history could not be read", threshold)
    if od["creator_prior_tx_count_capped"]:
        return signal("new_creator_wallet", label, "not found",
                      f"creator {od['creator']} sent 1,000 or more transactions before creating the token", threshold)
    if not od["creator_first_seen"]:
        return signal("new_creator_wallet", label, "found",
                      f"creator {od['creator']} had no transactions before creating the token", threshold)
    parse = lambda t: datetime.strptime(t, "%Y-%m-%dT%H:%M:%SZ")
    hours = (parse(od["created_at"]) - parse(od["creator_first_seen"])).total_seconds() / 3600
    return signal("new_creator_wallet", label, "found" if hours < NEW_WALLET_HOURS else "not found",
                  f"creator {od['creator']} first seen {od['creator_first_seen']}, {hours:,.1f} hours before "
                  f"creation, with {od['creator_prior_tx_count']} earlier transactions", threshold)


def collect(mint, result, args):
    ov = run(overview, mint, args, result)  # a non-mint address raises ValueError and stops here
    od = run(origin, mint, Namespace(max_pages=args.max_pages), result)
    hd = run(holders, mint, args, result)
    pd = run(pools, mint, args, result)
    signals = [*authority_signals(ov), extension_signal(ov), metadata_signal(ov), holder_signal(hd),
               liquidity_signal(pd), creator_signal(od)] if ov else []
    meta = ov.get("metadata") or {}
    result["data"] = {
        "signals_found": sum(s["status"] == "found" for s in signals),
        "signals_checked": sum(s["status"] in ("found", "not found") for s in signals),
        "signals": signals,
        "facts": {
            "name": meta.get("name"), "symbol": meta.get("symbol"), "token_program": ov.get("token_program"),
            "created_at": od.get("created_at"), "launchpad": od.get("launchpad"),
            "price_usd": pd.get("price_usd"), "liquidity_usd": pd.get("total_liquidity_usd"),
            "holder_count": hd.get("holder_count"),
        },
    }


def add_args(parser):
    parser.add_argument("--max-pages", type=int, default=10, help="origin lookup depth without Helius (default 10)")


if __name__ == "__main__":
    script(__doc__, collect, add_args)
