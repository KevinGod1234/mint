#!/usr/bin/env python3
"""Where a token came from: creation time, creator wallet, creating program
and launchpad, and how much the creator wallet did before."""

from common import HELIUS_API, SourceError, config, http_json, iso, known_programs, rpc, rpc_url, script

PAGE = 1000


def from_helius(mint, key):
    """Oldest parsed transactions of the mint, oldest first, in one call."""
    txs = http_json(f"{HELIUS_API}/addresses/{mint}/transactions?api-key={key}&sort-order=asc&limit=10")
    ok = [t for t in txs if not t.get("transactionError")]
    if not ok:
        raise SourceError("Helius returned no successful transactions for this mint")
    first = ok[0]
    programs = []
    for ix in first.get("instructions") or []:
        programs.append(ix.get("programId"))
        programs += [inner.get("programId") for inner in ix.get("innerInstructions") or []]
    return {"signature": first["signature"], "time": first.get("timestamp"), "creator": first.get("feePayer"),
            "programs": programs, "helius_type": first.get("type"), "helius_source": first.get("source")}


def oldest_signature(mint, max_pages):
    """Page back through the mint's signatures. Returns (oldest ok entry, complete, scanned)."""
    before, oldest, scanned = None, None, 0
    for _ in range(max_pages):
        sigs = rpc("getSignaturesForAddress", [mint, {"limit": PAGE, **({"before": before} if before else {})}])
        scanned += len(sigs)
        if not sigs:
            return oldest, True, scanned
        oldest = next((s for s in reversed(sigs) if s.get("err") is None), oldest)
        before = sigs[-1]["signature"]
        if len(sigs) < PAGE:
            return oldest, True, scanned
    return oldest, False, scanned


def from_rpc(signature):
    tx = rpc("getTransaction", [signature, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])
    if not tx:
        raise SourceError(f"transaction {signature} not found")
    message = tx["transaction"]["message"]
    programs = [ix.get("programId") for ix in message["instructions"]]
    for group in (tx.get("meta") or {}).get("innerInstructions") or []:
        programs += [ix.get("programId") for ix in group["instructions"]]
    return {"signature": signature, "time": tx.get("blockTime"), "creator": message["accountKeys"][0]["pubkey"],
            "programs": programs}


def creator_history(creator, signature):
    """How many transactions the creator sent before the creation, and when it was first seen."""
    sigs = rpc("getSignaturesForAddress", [creator, {"limit": PAGE, "before": signature}])
    if len(sigs) < PAGE:
        first = sigs[-1].get("blockTime") if sigs else None
        return {"creator_prior_tx_count": len(sigs), "creator_prior_tx_count_capped": False,
                "creator_first_seen": iso(first)}
    return {"creator_prior_tx_count": PAGE, "creator_prior_tx_count_capped": True, "creator_first_seen": None}


def collect(mint, result, args):
    known = known_programs()
    found = None
    key = config()["HELIUS_API_KEY"]
    if key:
        try:
            found = from_helius(mint, key)
            found["method"] = "Helius parsed history"
            result.source("Helius", HELIUS_API)
        except (SourceError, KeyError, TypeError, IndexError) as e:
            result.miss("Helius history", f"{e}; fell back to RPC paging", partial=False)
    if found is None:
        result.source("Solana RPC", rpc_url())
        oldest, complete, scanned = oldest_signature(mint, args.max_pages)
        if not oldest:
            raise SourceError("no transactions found for this mint")
        if not complete:
            result.miss("creation transaction",
                        f"stopped after {scanned:,} signatures ({args.max_pages} pages) before reaching it. "
                        "Set HELIUS_API_KEY or raise --max-pages")
            result["data"] = {"created_at": None, "creator": None, "launchpad": None,
                              "method": "RPC signature paging", "signatures_scanned": scanned,
                              "reached_creation": False, "oldest_seen_at": iso(oldest.get("blockTime")),
                              "oldest_seen_signature": oldest["signature"]}
            return
        found = from_rpc(oldest["signature"])
        found.update(method="RPC signature paging", signatures_scanned=scanned, reached_creation=complete)

    programs = list(dict.fromkeys(p for p in found.pop("programs") if p))
    launchpad = next((p for p in programs if known.get(p, {}).get("kind") == "launchpad"), None)
    data = {
        "created_at": iso(found.pop("time")),
        "creator": found.pop("creator"),
        "launchpad": known[launchpad]["name"] if launchpad else None,
        "launchpad_program": launchpad,
        "creation_signature": found.pop("signature"),
        **found,
    }
    if not launchpad:
        result.miss("launchpad", "no program in the creation transaction is listed in references/launchpads.md",
                    partial=False)
    result.source("Solana RPC", rpc_url())
    try:
        data.update(creator_history(data["creator"], data["creation_signature"]))
    except SourceError as e:
        result.miss("creator wallet history", str(e))
    data["programs_in_creation_tx"] = [{"program": p, "name": known.get(p, {}).get("name")} for p in programs]
    result["data"] = data


def add_args(parser):
    parser.add_argument("--max-pages", type=int, default=10,
                        help="pages of 1,000 signatures to scan without Helius (default 10)")


if __name__ == "__main__":
    script(__doc__, collect, add_args)
