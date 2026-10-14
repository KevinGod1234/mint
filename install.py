#!/usr/bin/env python3
"""Install from a clone: copies the skill into ~/.claude/skills and runs setup.
Same as: python3 skills/solana-token-intel/scripts/cli.py install"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "skills" / "solana-token-intel" / "scripts"))
import cli  # noqa: E402

sys.exit(cli.main(["install", *sys.argv[1:]]))
