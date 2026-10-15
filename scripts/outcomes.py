#!/usr/bin/env python3
"""What happened to coins like this one: pump.fun coins you looked up yourself,
measured on-chain at 1, 7 and 30 days. History with sample sizes, never a
prediction."""

import json
import os
import time

from common import (CONFIG_FILE, SourceError, account_bytes, accounts, b58decode, find_pda, from_iso,
                    iso, rpc, rpc_url, script)

PUMP = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"
SAMPLES_FILE = CONFIG_FILE.parent / "samples.jsonl"  # coins this user looked up; never leaves their machine
AGES = {"d1": 1, "d7": 7, "d30": 30}
ACTIVE_HOURS = 24
LOCAL_CHECKS = 30  # local samples re-measured per run, to stay inside the request budget


def measure(mints):
    """On-chain state now: {mint: {pump_curve, graduated, last_activity_at}}. One account call per 100 mints,
    one signature call per mint. A mint whose lookup fails is left out, never guessed."""
    curves = {m: find_pda([b"bonding-curve", b58decode(m)], PUMP) for m in mints}
    found = accounts(list(curves.values()))
    out = {}
    for m, curve in curves.items():
        acc = found.get(curve)
        on_curve = bool(acc) and acc["owner"] == PUMP
        try:
            sigs = rpc("getSignaturesForAddress", [m, {"limit": 1}])
        except SourceError as e:
            if e.status == "budget":
                raise
            continue
        out[m] = {"pump_curve": on_curve,
                  "graduated": bool(account_bytes(acc)[48]) if on_curve else None,  # bonding curve `complete` flag
                  "last_activity_at": iso(sigs[0].get("blockTime")) if sigs else None}
    return out


def outcome(state, record, now):
    """The record stored for one check."""
    last = state["last_activity_at"]
    active = bool(last) and now - from_iso(last) <= ACTIVE_HOURS * 3600
    return {"checked_at": iso(now), "age_days": round((now - from_iso(record["created_at"])) / 86400, 2),
            "graduated": state["graduated"], "active_24h": active}


def due(record, now):
    """Ages whose window (days to twice that) this record is in and has not been checked at.
    A missed window stays empty rather than holding a late reading under the wrong age."""
    age_days = (now - from_iso(record["created_at"])) / 86400
    return [k for k, days in AGES.items() if days <= age_days < 2 * days and k not in record]


def summarize(records):
    """Counts per age: how many were checked, graduated, and still active."""
    rows = {}
    for k in AGES:
        checked = [r[k] for r in records if k in r]
        rows[k] = {"n": len(checked), "graduated": sum(bool(c["graduated"]) for c in checked),
                   "active_24h": sum(c["active_24h"] for c in checked)}
    return rows


# -------------------------------------------------------------- local samples

def save_sample(mint, created_at):
    """Called after check and creator lookups. Keeps one line per coin, oldest lookup wins."""
    if not created_at or any(r["mint"] == mint for r in load_samples()):
        return
    try:
        SAMPLES_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with open(os.open(SAMPLES_FILE, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600), "a") as f:
            f.write(json.dumps({"mint": mint, "created_at": created_at, "sampled_at": iso(time.time())}) + "\n")
    except OSError:
        pass  # unwritable home: lookups still work, only the local sample is skipped


def load_samples():
    try:
        return [json.loads(line) for line in SAMPLES_FILE.read_text().splitlines() if line.strip()]
    except (OSError, ValueError):
        return []


def recheck_samples(result):
    samples, now = load_samples(), time.time()
    todo = [r for r in samples if due(r, now)][:LOCAL_CHECKS]
    if todo:
        states = measure([r["mint"] for r in todo])
        for r in (r for r in todo if r["mint"] in states):
            for k in due(r, now):
                r[k] = outcome(states[r["mint"]], r, now)
        SAMPLES_FILE.write_text("".join(json.dumps(r) + "\n" for r in samples))
    waiting = sum(bool(due(r, now)) for r in samples)
    if waiting:
        result.miss("some of your samples", f"{waiting} are due for a check; run again to measure more "
                    f"({LOCAL_CHECKS} per run)", partial=False)
    return samples


# --------------------------------------------------------------------- lookup

def collect(mint, result, args):
    now = time.time()
    result.source("Solana RPC", rpc_url())
    state = measure([mint]).get(mint)
    if not state:
        raise SourceError("this coin's on-chain state could not be read")
    data = {"this_coin": {"pump_fun": state["pump_curve"], "graduated_now": state["graduated"],
                          "last_activity_at": state["last_activity_at"]}}
    samples = recheck_samples(result)
    data["yours"] = {"coins": len(samples), "file": str(SAMPLES_FILE), **summarize(samples)}
    if not state["pump_curve"]:
        result.miss("a matching group", "this coin has no pump.fun bonding curve, so the graduation counts "
                    "describe a different kind of coin", partial=False)
    result["data"] = data


if __name__ == "__main__":
    script(__doc__, collect)
