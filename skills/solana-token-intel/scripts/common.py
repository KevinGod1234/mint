"""Shared code: config, HTTP with retries, Solana helpers, JSON output, key
redaction, and the one terminal style every screen uses."""

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
import textwrap
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

VERSION = "0.1.0"
SKILL_DIR = Path(__file__).resolve().parent.parent
REFERENCES = SKILL_DIR / "references"
CONFIG_FILE = (Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
               / "solana-token-intel" / ".env")
CONFIG_VARS = ("SOLANA_RPC_URL", "HELIUS_API_KEY", "BIRDEYE_API_KEY", "PASSPORT_RPC_URL")
PUBLIC_RPC = "https://api.mainnet-beta.solana.com"
DEVNET_RPC = "https://api.devnet.solana.com"
HELIUS_API = "https://api-mainnet.helius-rpc.com/v0"
BIRDEYE_API = "https://public-api.birdeye.so"
GECKO_API = "https://api.geckoterminal.com/api/v2"
DEXSCREENER_API = "https://api.dexscreener.com"
USER_AGENT = f"solana-token-intel/{VERSION}"  # DEX Screener rejects Python's default agent

SPL_TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
METAPLEX = "metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s"
SYSTEM_PROGRAM = "11111111111111111111111111111111"
BURN_ADDRESS = "1nc1nerator11111111111111111111111111111111"


class SourceError(Exception):
    """A data source failed. The message is already safe to show."""


# ---------------------------------------------------------------- config

def config():
    """Environment variables win over the config file. Only our own variables are read."""
    values = {}
    try:
        for line in CONFIG_FILE.read_text().splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and key.strip() in CONFIG_VARS:
                values[key.strip()] = value.strip().strip("'\"")
    except OSError:
        pass
    for key in CONFIG_VARS:
        if os.environ.get(key):
            values[key] = os.environ[key].strip()
    return {key: values.get(key) or None for key in CONFIG_VARS}


def redact(text):
    """Remove every configured secret and any api-key style query value from text."""
    text = str(text)
    for value in config().values():
        if value and len(value) >= 6:
            text = text.replace(value, "***")
    return re.sub(r"(?i)(api[-_]?key=)[^&\s\"']+", r"\1***", text)


def host(url):
    """Scheme and host only: the safe way to name a URL that may hold a key."""
    parts = urllib.parse.urlsplit(url)
    return f"{parts.scheme}://{parts.hostname}"


# ------------------------------------------------------------------ HTTP

def http_json(url, *, data=None, headers=None, retries=5, timeout=30):
    """GET (or POST when data is given) JSON with backoff on 429 and 5xx."""
    body = json.dumps(data).encode() if data is not None else None
    head = {"accept": "application/json", "user-agent": USER_AGENT}
    if body:
        head["content-type"] = "application/json"
    head.update(headers or {})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, body, head), timeout=timeout) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(_retry_after(e.headers.get("retry-after"), attempt))
                continue
            note = " (rate limited, retries used up)" if e.code == 429 else ""
            raise SourceError(f"{host(url)} returned HTTP {e.code}{note}") from None
        except (urllib.error.URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as e:
            if attempt < retries:
                time.sleep(2 ** attempt)
                continue
            raise SourceError(f"{host(url)} could not be reached: {redact(getattr(e, 'reason', e))}") from None


def _retry_after(header, attempt):
    backoff = min(2 ** (attempt + 1), 30)  # 2+4+8+16+30 s: outlasts per-minute windows such as GeckoTerminal's
    try:
        return min(max(float(header), backoff), 30)  # GeckoTerminal sends "retry-after: 0" while still limiting
    except (TypeError, ValueError):
        return backoff


def rpc_url():
    return config()["SOLANA_RPC_URL"] or PUBLIC_RPC


def rpc(method, params, url=None, retries=4):
    """One JSON-RPC call. Some RPCs report rate limits inside a 200 response."""
    url = url or rpc_url()
    hint = "; set SOLANA_RPC_URL to a private RPC (run: cli.py setup)" if url == PUBLIC_RPC else ""
    for attempt in range(retries + 1):
        try:
            reply = http_json(url, data={"jsonrpc": "2.0", "id": 1, "method": method, "params": params},
                              retries=retries)
        except SourceError as e:
            raise SourceError(f"RPC {method}: {e}{hint if '429' in str(e) else ''}") from None
        error = reply.get("error")
        if not error:
            return reply.get("result")
        if error.get("code") in (429, -32429) and attempt < retries:
            time.sleep(2 ** attempt)
            continue
        limited = error.get("code") in (429, -32429)
        raise SourceError(f"RPC {method} on {host(url)} failed: {redact(error.get('message', error))}"
                          f"{hint if limited else ''}")


def accounts(addresses, url=None, encoding="base64"):
    """getMultipleAccounts in chunks of 100; returns {address: account or None}."""
    out = {}
    addresses = list(dict.fromkeys(addresses))
    for i in range(0, len(addresses), 100):
        chunk = addresses[i:i + 100]
        values = rpc("getMultipleAccounts", [chunk, {"encoding": encoding}], url)["value"]
        out.update(zip(chunk, values))
    return out


def account_bytes(account):
    return base64.b64decode(account["data"][0]) if account else b""


# ---------------------------------------------------------------- Solana

B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(raw):
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = B58[r] + out
    return "1" * (len(raw) - len(raw.lstrip(b"\0"))) + out


def b58decode(text):
    n = 0
    for ch in text:
        if ch not in B58:
            raise ValueError(f"not base58: {text!r}")
        n = n * 58 + B58.index(ch)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return b"\0" * (len(text) - len(text.lstrip("1"))) + raw


def pubkey(text):
    """Validate a Solana address from user input; returns it unchanged."""
    try:
        if len(b58decode(text)) == 32:
            return text
    except ValueError:
        pass
    raise ValueError(f"not a Solana address: {text!r}")


_P = 2 ** 255 - 19
_D = -121665 * pow(121666, _P - 2, _P) % _P


def on_curve(raw):
    """True when 32 bytes decode to an ed25519 point (a normal wallet key)."""
    y = int.from_bytes(raw, "little") & ((1 << 255) - 1)
    if y >= _P:
        return False
    y2 = y * y % _P
    x2 = (y2 - 1) * pow(_D * y2 + 1, _P - 2, _P) % _P
    return x2 == 0 or pow(x2, (_P - 1) // 2, _P) == 1


def find_pda(seeds, program):
    program_raw = b58decode(program)
    for bump in range(255, -1, -1):
        digest = hashlib.sha256(b"".join(seeds) + bytes([bump]) + program_raw + b"ProgramDerivedAddress").digest()
        if not on_curve(digest):
            return b58encode(digest)
    raise ValueError("no PDA found")


def known_programs():
    """Program IDs from references/launchpads.md: {program_id: {name, kind}}."""
    table = {}
    for line in (REFERENCES / "launchpads.md").read_text().splitlines():
        cells = [c.strip().strip("`") for c in line.strip().strip("|").split("|")]
        if len(cells) >= 3 and re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", cells[2]):
            table[cells[2]] = {"name": cells[0], "kind": cells[1]}
    return table


def iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts is not None else None


def now_iso():
    return iso(time.time())


# ---------------------------------------------------------------- results

class Result(dict):
    """The one JSON shape every script prints."""

    def __init__(self, script, mint):
        super().__init__(script=script, mint=mint, fetched_at=now_iso(), data={},
                         sources=[], missing=[], partial=False)

    def source(self, name, url):
        entry = {"name": name, "url": host(url)}
        if entry not in self["sources"]:
            self["sources"].append(entry)

    def miss(self, what, why, partial=True):
        self["missing"].append({"what": what, "why": redact(why)})
        self["partial"] = self["partial"] or partial

    def merge(self, other):
        for s in other["sources"]:
            if s not in self["sources"]:
                self["sources"].append(s)
        self["missing"] += other["missing"]
        self["partial"] = self["partial"] or other["partial"]


def script(description, collect, add_args=None):
    """Parse args, run collect(mint, result, args), print one JSON object (or --pretty)."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("mint", help="token mint address")
    parser.add_argument("--pretty", action="store_true", help="human-readable view instead of JSON")
    if add_args:
        add_args(parser)
    args = parser.parse_args()
    try:
        result = Result(Path(sys.argv[0]).stem, pubkey(args.mint))
        collect(result["mint"], result, args)
    except (SourceError, ValueError) as e:
        fail(str(e))
    except (KeyError, TypeError, IndexError) as e:
        fail(f"a source sent a response in an unexpected shape ({type(e).__name__}: {e})")
    except KeyboardInterrupt:
        fail("interrupted")
    if args.pretty:
        render(result)
    else:
        print(json.dumps(result, indent=2))


def fail(message):
    print(json.dumps({"error": redact(message)}), file=sys.stderr)
    sys.exit(1)


# ------------------------------------------------------------------ style
# One palette for every screen a person sees: setup, doctor, tests and
# --pretty views. Change it here and everything follows.

PALETTE = {
    "brand": "1;38;5;141",   # bold violet: titles and the ◆ mark
    "accent": "38;5;117",    # light blue: addresses, values to notice
    "label": "38;5;250",     # light grey: keys and column heads
    "muted": "38;5;244",     # grey: hints, secondary text
    "ok": "38;5;114",        # green: check passed, set, endorsed
    "warn": "38;5;221",      # amber: signal found, partial, not set
    "bad": "38;5;203",       # red: failed, disavowed
}
# Values that always get the same color wherever they appear.
VALUE_ROLES = {"found": "warn", "not found": "muted", "not checked": "muted", "not applicable": "muted",
               "mixed": "warn",
               "endorsed": "ok", "disavowed": "bad", "no record": "muted",
               "wallet": "label", "program account": "accent"}


def _supports(stream, text):
    try:
        text.encode(stream.encoding or "ascii")
        return True
    except (UnicodeEncodeError, LookupError):
        return False


COLOR = sys.stdout.isatty() and not os.environ.get("NO_COLOR") and os.environ.get("TERM") != "dumb"
if COLOR and os.name == "nt":
    os.system("")  # switches older Windows consoles into ANSI color mode
UNICODE = _supports(sys.stdout, "◆─✓✗•…▁█")
MARK = {"ok": "✓", "warn": "!", "bad": "✗", "muted": "•", "brand": "◆"} if UNICODE else \
       {"ok": "+", "warn": "!", "bad": "x", "muted": "-", "brand": "*"}
RULE = "─" if UNICODE else "-"
ELLIPSIS = "…" if UNICODE else "..."


def paint(text, role):
    return f"\033[{PALETTE[role]}m{text}\033[0m" if COLOR and role else str(text)


def _plain(text):
    return re.sub(r"\033\[[0-9;]*m", "", text)


def width():
    return min(shutil.get_terminal_size((88, 24)).columns, 100)


def banner(title, subtitle=""):
    print()
    print(f" {paint(MARK['brand'], 'brand')} {paint('solana-token-intel', 'brand')}  {paint(title, 'label')}"
          + (f"  {paint(subtitle, 'accent')}" if subtitle else ""))
    print(" " + paint(RULE * (width() - 2), "muted"))


def heading(text):
    print(f"\n {paint(text.upper(), 'brand')}")


def line(role, label, value="", note=""):
    """One status row: mark, label, value, note. Every screen uses this."""
    label = f"{label:<22}" if value or note else label
    print(f"  {paint(MARK[role], role)} {paint(label, 'label')} {value}"
          + (f"  {paint(note, 'muted')}" if note else ""))


def summary(role, title, hint=""):
    """The closing line of a screen: one mark, a colored title, a muted hint."""
    print(f"  {paint(MARK[role], role)} {paint(title, role)}" + (f"  {paint(hint, 'muted')}" if hint else ""))


def note(role, title, detail, tag=""):
    """A titled entry with wrapped detail underneath: signals and missing data."""
    print(f"  {paint(MARK[role], role)} {paint(title, 'label')}" + (f"  {paint(tag, role)}" if tag else ""))
    for chunk in textwrap.wrap(str(detail), width() - 8):
        print("      " + paint(chunk, "muted"))


def kv(key, value, indent=2):
    print(" " * indent + paint(f"{key.replace('_', ' '):<30}", "label") + " " + fmt(value))


def fmt(value):
    if value is None:
        return paint("none", "muted")
    if isinstance(value, bool):
        return paint("yes", "accent") if value else paint("no", "muted")
    if isinstance(value, int):
        return f"{value:,}"
    if isinstance(value, float):
        return f"{value:,.2f}" if abs(value) >= 1 else f"{value:.6g}"
    text = str(value)
    if text in VALUE_ROLES:
        return paint(text, VALUE_ROLES[text])
    if re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", text):
        return paint(text, "accent")
    return text


def short(text, size):
    text = str(text)
    if len(text) <= size:
        return text
    if re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", text) and size >= 11:  # addresses: keep both ends
        half = (size - len(ELLIPSIS)) // 2
        return text[:half] + ELLIPSIS + text[-half:]
    return text[:size - len(ELLIPSIS)] + ELLIPSIS


def table(rows, max_rows=15):
    columns = list(dict.fromkeys(k for r in rows for k in r if not isinstance(r[k], (dict, list))))
    cell = lambda v: _plain(fmt(v))
    widths, used = {}, 0
    for c in columns:  # columns are in priority order: keep them while they fit
        w = min(30, max(len(c), *(len(cell(r.get(c))) for r in rows[:max_rows])))
        if used + w > width() - 4 and widths:
            break
        widths[c], used = w, used + w + 2
    print("  " + "  ".join(paint(short(c.replace("_", " "), widths[c]).ljust(widths[c]), "label") for c in widths))
    for r in rows[:max_rows]:
        out = []
        for c in widths:
            text = short(cell(r.get(c)), widths[c])
            value = str(r.get(c))
            role = VALUE_ROLES.get(value) or ("accent" if re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", value)
                                              else "muted" if r.get(c) is None else None)
            out.append(paint(text, role) + " " * (widths[c] - len(text)))
        print("  " + "  ".join(out))
    if len(rows) > max_rows:
        print("  " + paint(f"{ELLIPSIS} {len(rows) - max_rows} more in the JSON output", "muted"))


def sparkline(values):
    if not values or not UNICODE:
        return ""
    low, high = min(values), max(values)
    bars = "▁▂▃▄▅▆▇█"
    return "".join(bars[int((v - low) / (high - low) * 7) if high > low else 3] for v in values)


def render(result):
    """The --pretty view of any script's result."""
    banner(result["script"], result["mint"])
    print("  " + paint(f"fetched {result['fetched_at']}", "muted"))
    _walk(result["data"], 2)
    if result["sources"]:
        heading("sources")
        for s in result["sources"]:
            line("muted", s["name"], paint(s["url"], "muted"))
    if result["missing"]:
        heading("not checked or incomplete")
        for m in result["missing"]:
            note("warn", m["what"], m["why"])
    if result["partial"]:
        print("\n  " + paint("Partial result: some data could not be fetched.", "warn"))
    print()


def _walk(data, indent):
    for key, value in data.items():
        if isinstance(value, dict):
            if indent == 2:
                heading(key.replace("_", " "))
            else:
                print(" " * indent + paint(key.replace("_", " "), "label"))
            child = indent if indent == 2 else indent + 2
            _walk(value, child) if value else print(" " * child + paint("none", "muted"))
        elif key == "signals":
            heading("signals")
            for sig in value:
                role = {"found": "warn"}.get(sig["status"], "muted")
                note(role, sig["label"], sig["evidence"], sig["status"])
        elif isinstance(value, list) and value and all(isinstance(v, dict) for v in value):
            heading(key.replace("_", " "))
            if key == "candles":
                closes = [c["close"] for c in value if c.get("close") is not None]
                print("  " + paint(sparkline(closes[-(width() - 6):]), "accent"))
                value = value[-10:]
                print("  " + paint("last 10 candles", "muted"))
            table(value)
        elif isinstance(value, list):
            kv(key, ", ".join(str(v) for v in value) if value else None, indent)
        else:
            kv(key, value, indent)
