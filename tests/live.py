#!/usr/bin/env python3
"""Release check: run every script against every token in tests/tokens.md.
Live network calls; takes a few minutes because it paces itself for free rate limits."""

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))
from common import banner, heading, line, paint, summary  # noqa: E402

ALL = ["overview", "origin", "history", "pools", "holders", "risk", "creator"]


def tokens():
    for row in (ROOT / "tests" / "tokens.md").read_text().splitlines():
        cells = [c.strip().strip("`") for c in row.strip().strip("|").split("|")]
        if len(cells) >= 3 and re.fullmatch(r"[1-9A-HJ-NP-Za-km-z]{32,44}", cells[2]):
            yield cells[0], cells[1], cells[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scripts", nargs="+", choices=ALL, default=ALL)
    parser.add_argument("--pause", type=float, default=3, help="seconds between runs (default 3)")
    args = parser.parse_args()
    banner("release check", f"{len(list(tokens()))} tokens")
    failed = partial = passed = 0
    for kind, name, mint in tokens():
        heading(f"{kind} · {name}")
        for script in args.scripts:
            start = time.monotonic()
            run = subprocess.run([sys.executable, str(SCRIPTS / f"{script}.py"), mint], capture_output=True, text=True)
            took = f"{time.monotonic() - start:.1f} s"
            try:
                out = json.loads(run.stdout) if run.returncode == 0 else None
            except json.JSONDecodeError:
                out = None
            if out is None:
                failed += 1
                error = (run.stderr.strip().splitlines() or ["no output"])[-1]
                line("bad", script, paint("failed", "bad"), error[:120])
            elif out["partial"]:
                partial += 1
                line("warn", script, paint("partial", "warn"), f"{took} · " + "; ".join(m["what"] for m in out["missing"]))
            else:
                passed += 1
                line("ok", script, "ok", took)
            time.sleep(args.pause)
    print()
    role = "bad" if failed else "warn" if partial else "ok"
    summary(role, f"{passed} ok, {partial} partial, {failed} failed",
            "Partial is expected without keys; read each reason." if partial else "")
    print()
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
