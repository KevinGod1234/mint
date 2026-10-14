---
description: Add API keys or a private RPC URL for mint.
allowed-tools: Bash(mint keys)
disable-model-invocation: true
---

Run `mint keys` and show the user its output. It creates their private keys
file (readable only by them) and lists which keys are set, never the values.

Then tell them, in a few short lines:

1. Open the file shown in any text editor and paste each value after its `=`.
2. All keys are optional. A free Helius account gives both `SOLANA_RPC_URL`
   (their RPC URL) and `HELIUS_API_KEY`, which fill most gaps.
3. Save the file, then run `/mint:doctor` to check.

Never ask for a key, never accept one in the chat, and never read, print or
edit the keys file yourself. If a key is pasted into the chat, tell the user to
remove it and rotate it.
