#!/usr/bin/env python3
"""mint: set up keys and check every data source.

  keys      create your private keys file and show which keys are set
  setup     type your keys in a terminal (input stays hidden)
  doctor    check the config, this hour's usage and every data source
"""

import argparse
import getpass
import os
import re
import stat
import sys
import time

from common import (BIRDEYE_API, CONFIG_FILE, OLD_CONFIG_FILE, DEFAULT_HOURLY_BUDGET, DEXSCREENER_API, GECKO_API, HELIUS_API,
                    PUBLIC_RPC, VERSION, SourceError, banner, config, heading, host, hourly_budget, http_json, line,
                    paint, redact, rpc, summary, usage)

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL = "So11111111111111111111111111111111111111112"

FIELDS = [  # name, what it is for, what happens without it, kind
    ("SOLANA_RPC_URL", "RPC for mints, holders and transactions.",
     "Without it: the public RPC. Slow, and holder lists do not work.", "url"),
    ("HELIUS_API_KEY", "Full transaction history for origin lookups.",
     "Without it: origin pages back through up to 10,000 signatures.", "key"),
    ("BIRDEYE_API_KEY", "Price history across all pools.",
     "Without it: GeckoTerminal, most liquid pool only.", "key"),
    ("MINT_MAX_CALLS_PER_HOUR", "Safety budget: requests per source per hour, across all lookups.",
     f"Without it: {DEFAULT_HOURLY_BUDGET}. Stops a runaway loop from burning credits.", "number"),
]


def valid(kind, value):
    if kind == "number":
        return value.isdigit() and 1 <= int(value) <= 100000
    if kind == "url":
        return bool(re.fullmatch(r"https://\S+|http://(localhost|127\.0\.0\.1)(:\d+)?\S*", value))
    return bool(re.fullmatch(r"[A-Za-z0-9_\-.]{8,200}", value))


def shown(kind, value):
    """What setup may show about a saved value: never the key itself."""
    if not value:
        return paint("not set", "muted")
    if kind == "number":
        return paint(value, "ok")
    return paint(f"set ({host(value)})" if kind == "url" else "set", "ok")


def write_config(values):
    """Every variable with a comment saying what it is for, so the file can be edited by hand."""
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lines = ["# mint: your private keys. Only you can read this file. Never paste these into a chat.",
             "# Everything is optional. Put the value after the = sign and save."]
    for name, purpose, without, _ in FIELDS:
        lines += ["", f"# {purpose} {without}", f"{name}={values.get(name) or ''}"]
    fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(CONFIG_FILE, 0o600)


def setup(_args=None):
    banner("setup", f"v{VERSION}")
    if not sys.stdin.isatty():
        line("warn", "Setup needs a terminal.", "", "Use /mint:setup in Claude Code to edit the keys file instead.")
        return 1
    print(f"  Keys are saved to {paint(CONFIG_FILE, 'accent')}, readable only by you.")
    print("  " + paint("Everything is optional. Free sources work without any key.", "muted"))
    print("  " + paint("Input is hidden. Enter keeps the current value, a single - clears it.", "muted"))
    current = config()
    values = dict(current)
    for name, purpose, without, kind in FIELDS:
        heading(name)
        print(f"  {purpose}\n  {paint(without, 'muted')}")
        print(f"  current: {shown(kind, current[name])}")
        for _ in range(3):
            entered = getpass.getpass(f"  {paint('›', 'accent')} new value: ").strip()
            if entered in ("", "-") or valid(kind, entered):
                break
            line("bad", "That does not look like a valid "
                 + {"url": "https URL", "number": "whole number"}.get(kind, "key") + ".")
        else:
            line("warn", "Kept the current value.")
            continue
        if entered == "-":
            values[name] = None
        elif entered:
            values[name] = entered
        print(f"  saved: {shown(kind, values[name])}")
    write_config(values)
    if any(os.environ.get(k) for k, *_ in FIELDS):
        line("warn", "Some variables are also set in your shell; those win over the file.")
    print()
    summary("ok", "Saved.", "Checking sources next.")
    return doctor()


def timed(check):
    start = time.monotonic()
    try:
        detail = check()
        return True, detail, f"{(time.monotonic() - start) * 1000:,.0f} ms"
    except (SourceError, KeyError, TypeError, IndexError, ValueError) as e:
        return False, redact(e), ""


def doctor(_args=None):
    cfg = config()
    banner("doctor", f"v{VERSION}")
    problems = 0

    heading("setup")
    ok = sys.version_info >= (3, 8)
    problems += not ok
    line("ok" if ok else "bad", "Python", sys.version.split()[0], "" if ok else "needs 3.8 or newer")
    in_use = CONFIG_FILE if CONFIG_FILE.exists() else OLD_CONFIG_FILE if OLD_CONFIG_FILE.exists() else None
    if in_use:
        private = os.name == "nt" or not in_use.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO)
        note = "" if private else "readable by others: run chmod 600 on it"
        if in_use == OLD_CONFIG_FILE:
            note = "0.1 location, still read; /mint:setup copies it to the new one"
        line("ok" if private else "warn", "Config file", paint(in_use, "accent"), note)
    else:
        line("muted", "Config file", paint("not created", "muted"), "optional; /mint:setup adds keys")
    for name, _, without, kind in FIELDS:
        line("ok" if cfg[name] else "muted", name, shown(kind, cfg[name]), "" if cfg[name] else without)

    heading("usage this hour")
    used, limit = usage(), hourly_budget()
    if not any(used.values()):
        line("muted", "No requests yet", "", f"budget {limit} per source per hour")
    for name, stamps in sorted(used.items()):
        if stamps:
            role = "bad" if len(stamps) >= limit else "warn" if len(stamps) >= limit * 0.8 else "ok"
            line(role, name, f"{len(stamps)} / {limit}")

    heading("sources")
    rpc_url = cfg["SOLANA_RPC_URL"] or PUBLIC_RPC
    checks = [
        ("Solana RPC", lambda: f"slot {rpc('getSlot', [], rpc_url, retries=1):,} · {host(rpc_url)}", True),
        ("Holder lists", lambda: rpc("getTokenLargestAccounts", [USDC], rpc_url, retries=0) and
         "available on this RPC", bool(cfg["SOLANA_RPC_URL"])),
        ("GeckoTerminal", lambda: http_json(f"{GECKO_API}/networks?page=1", retries=1) and "free, 30 calls/min", True),
        ("DEX Screener", lambda: http_json(f"{DEXSCREENER_API}/token-pairs/v1/solana/{USDC}", retries=1)
         and "free", True),
        ("Helius", lambda: http_json(f"{HELIUS_API}/addresses/{USDC}/transactions?api-key="
                                     f"{cfg['HELIUS_API_KEY']}&limit=1", retries=1) and "key works",
         bool(cfg["HELIUS_API_KEY"])),
        ("Birdeye", lambda: http_json(f"{BIRDEYE_API}/defi/ohlcv?address={SOL}&type=1D&time_from="
                                      f"{int(time.time()) - 172800}&time_to={int(time.time())}", retries=1,
                                      headers={"X-API-KEY": cfg["BIRDEYE_API_KEY"], "x-chain": "solana"})["success"]
         and "key works", bool(cfg["BIRDEYE_API_KEY"])),
    ]
    for name, check, needed in checks:
        if not needed:
            if name == "Holder lists":
                line("warn", name, paint("not available", "warn"), "the public RPC refuses this; set SOLANA_RPC_URL")
            else:
                line("muted", name, paint("skipped", "muted"), "no key set")
            continue
        passed, detail, took = timed(check)
        problems += not passed
        line("ok" if passed else "bad", name, str(detail) if passed else paint("failed", "bad"),
             took if passed else str(detail))

    print()
    if problems:
        role, title, hint = "warn", f"{problems} check{'s' if problems > 1 else ''} need attention.", \
            "Lookups still run; results list what could not be checked."
    else:
        role, title, hint = "ok", "Ready.", "Try /mint:check <mint address>."
    summary(role, title, hint)
    print()
    return 1 if problems else 0


def keys(_args=None):
    """Create the keys file if needed and report which keys are set. Never prints a value."""
    banner("keys", f"v{VERSION}")
    created = not CONFIG_FILE.exists()
    if created:
        write_config(config())  # carries over keys from the v0.1 location or the environment
    os.chmod(CONFIG_FILE, 0o600)
    line("ok", "Keys file", paint(CONFIG_FILE, "accent"), "created, readable only by you" if created else "")
    cfg = config()
    for name, _, without, kind in FIELDS:
        line("ok" if cfg[name] else "muted", name, shown(kind, cfg[name]), "" if cfg[name] else without)
    print()
    summary("muted", "Open the file in a text editor, paste values after the = signs, and save.",
            "Then run /mint:doctor.")
    print()
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cli.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("keys", help="create your private keys file and show which keys are set")
    sub.add_parser("setup", help="type your keys in a terminal (input stays hidden)")
    sub.add_parser("doctor", help="check the config and every data source")
    args = parser.parse_args(argv)
    try:
        return {"keys": keys, "setup": setup, "doctor": doctor}[args.command](args)
    except (KeyboardInterrupt, EOFError):
        print("\n  " + paint("Stopped. Nothing else was changed.", "muted"))
        return 130


if __name__ == "__main__":
    sys.exit(main())
