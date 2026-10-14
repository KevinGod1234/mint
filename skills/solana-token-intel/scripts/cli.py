#!/usr/bin/env python3
"""solana-token-intel: install, set up keys, and check every data source.

  install   copy the skill into ~/.claude/skills, then run setup
  setup     save your RPC URL and API keys (typed input stays hidden)
  doctor    check the config and every data source
"""

import argparse
import getpass
import os
import re
import shutil
import stat
import sys
import time
from pathlib import Path

from common import (BIRDEYE_API, CONFIG_FILE, DEVNET_RPC, DEXSCREENER_API, GECKO_API, HELIUS_API, PUBLIC_RPC,
                    SKILL_DIR, VERSION, SourceError, banner, config, heading, host, http_json, line, paint,
                    redact, rpc, summary)

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
SOL = "So11111111111111111111111111111111111111112"
PASSPORT_PROGRAM = "2nke6euXvAnbtdtcbbk8N2Z3SRLuR7i67VYmSdcY5kwj"
INSTALL_DIR = Path.home() / ".claude" / "skills" / "solana-token-intel"

FIELDS = [  # name, what it is for, what happens without it, kind
    ("SOLANA_RPC_URL", "RPC for mints, holders and transactions.",
     "Without it: the public RPC. Slow, and holder lists do not work.", "url"),
    ("HELIUS_API_KEY", "Full transaction history for origin lookups.",
     "Without it: origin pages back through up to 10,000 signatures.", "key"),
    ("BIRDEYE_API_KEY", "Price history across all pools.",
     "Without it: GeckoTerminal, most liquid pool only.", "key"),
    ("PASSPORT_RPC_URL", "RPC for Artist Passport lookups.",
     "Without it: devnet, until the passport is on mainnet.", "url"),
]


def valid(kind, value):
    if kind == "url":
        return bool(re.fullmatch(r"https://\S+|http://(localhost|127\.0\.0\.1)(:\d+)?\S*", value))
    return bool(re.fullmatch(r"[A-Za-z0-9_\-.]{8,200}", value))


def shown(kind, value):
    """What setup may show about a saved value: never the key itself."""
    if not value:
        return paint("not set", "muted")
    return paint(f"set ({host(value)})" if kind == "url" else "set", "ok")


def ask(prompt):
    return input(f"  {paint('›', 'accent')} {prompt}").strip()


def write_config(values):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    lines = ["# solana-token-intel keys. Written by cli.py setup. Keep this file private."]
    lines += [f"{k}={v}" for k, v in values.items() if v]
    fd = os.open(CONFIG_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write("\n".join(lines) + "\n")
    os.chmod(CONFIG_FILE, 0o600)


def setup(_args=None):
    banner("setup", f"v{VERSION}")
    if not sys.stdin.isatty():
        line("warn", "Setup needs a terminal.", "", "Run it yourself: python3 " + str(Path(__file__)) + " setup")
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
            line("bad", "That does not look like a valid " + ("https URL" if kind == "url" else "key") + ".")
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
    if CONFIG_FILE.exists():
        private = os.name == "nt" or not CONFIG_FILE.stat().st_mode & (stat.S_IRWXG | stat.S_IRWXO)
        line("ok" if private else "warn", "Config file", paint(CONFIG_FILE, "accent"),
             "" if private else "readable by others: run chmod 600 on it")
    else:
        line("muted", "Config file", paint("not created", "muted"), "optional; run setup to add keys")
    for name, _, without, kind in FIELDS:
        line("ok" if cfg[name] else "muted", name, shown(kind, cfg[name]), "" if cfg[name] else without)

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
        ("Artist Passport", lambda: (rpc("getAccountInfo", [PASSPORT_PROGRAM, {"encoding": "base64"}],
                                         cfg["PASSPORT_RPC_URL"] or DEVNET_RPC, retries=1) or {}).get("value")
         and f"program found · {'devnet' if not cfg['PASSPORT_RPC_URL'] else host(cfg['PASSPORT_RPC_URL'])}", True),
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
        role, title, hint = "ok", "Ready.", 'Ask Claude: "what is this token?" with a mint address.'
    summary(role, title, hint)
    print()
    return 1 if problems else 0


def install(args):
    banner("install", f"v{VERSION}")
    target = Path(args.target).expanduser()
    if SKILL_DIR.resolve() == target.resolve():
        line("ok", "Already installed", paint(target, "accent"))
    else:
        if target.exists():
            if not sys.stdin.isatty() or ask(f"Replace {target}? [y/N] ").lower() != "y":
                line("muted", "Kept the existing copy.", paint(target, "accent"))
                return 0
            shutil.rmtree(target)
        shutil.copytree(SKILL_DIR, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".env"))
        line("ok", "Skill copied", paint(target, "accent"))
    line("muted", "Start a new Claude Code session to load it.")
    if args.no_setup or not sys.stdin.isatty():
        line("muted", "Add keys later", paint(f"python3 {target / 'scripts' / 'cli.py'} setup", "accent"))
        return 0
    print()
    return setup()


def main(argv=None):
    parser = argparse.ArgumentParser(prog="cli.py", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("install", help="copy the skill into ~/.claude/skills, then run setup")
    p.add_argument("--target", default=str(INSTALL_DIR), help=f"install folder (default {INSTALL_DIR})")
    p.add_argument("--no-setup", action="store_true", help="skip the key setup step")
    sub.add_parser("setup", help="save your RPC URL and API keys")
    sub.add_parser("doctor", help="check the config and every data source")
    args = parser.parse_args(argv)
    try:
        return {"install": install, "setup": setup, "doctor": doctor}[args.command](args)
    except (KeyboardInterrupt, EOFError):
        print("\n  " + paint("Stopped. Nothing else was changed.", "muted"))
        return 130


if __name__ == "__main__":
    sys.exit(main())
