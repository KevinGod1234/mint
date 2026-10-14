#!/usr/bin/env python3
"""Artist Passport records for a mint: which verified artists endorse or
disavow it, with each passport's age. Reads the riff_passport program using
its published IDL (references/riff_passport.json)."""

import json
import struct
import time

from common import (DEVNET_RPC, REFERENCES, SourceError, account_bytes, accounts, b58encode, config, iso,
                    rpc, script)

IDL = json.loads((REFERENCES / "riff_passport.json").read_text())
PROGRAM = IDL["address"]
TYPES = {t["name"]: t["type"] for t in IDL["types"]}
DISCRIMINATOR = {a["name"]: bytes(a["discriminator"]) for a in IDL["accounts"]}
FIXED = {"bool": 1, "u8": 1, "i8": 1, "u16": 2, "i16": 2, "u32": 4, "i32": 4, "u64": 8, "i64": 8,
         "u128": 16, "i128": 16, "pubkey": 32}
INTS = {"u8": "<B", "i8": "<b", "u16": "<H", "i16": "<h", "u32": "<I", "i32": "<i", "u64": "<Q", "i64": "<q"}


def decode(ty, raw, pos):
    """Borsh-decode one IDL type at pos; returns (value, new pos)."""
    if isinstance(ty, str) and ty in INTS:
        return struct.unpack_from(INTS[ty], raw, pos)[0], pos + FIXED[ty]
    if isinstance(ty, str) and ty in ("u128", "i128"):
        return int.from_bytes(raw[pos:pos + 16], "little", signed=ty == "i128"), pos + 16
    if ty == "bool":
        return raw[pos] == 1, pos + 1
    if ty == "pubkey":
        return b58encode(raw[pos:pos + 32]), pos + 32
    if ty in ("string", "bytes"):
        size = struct.unpack_from("<I", raw, pos)[0]
        chunk = raw[pos + 4:pos + 4 + size]
        return (chunk.decode("utf-8", "replace") if ty == "string" else chunk.hex()), pos + 4 + size
    if "array" in ty:
        inner, count = ty["array"]
        if inner == "u8":
            return raw[pos:pos + count].hex(), pos + count
        out = []
        for _ in range(count):
            value, pos = decode(inner, raw, pos)
            out.append(value)
        return out, pos
    if "vec" in ty:
        count, pos = struct.unpack_from("<I", raw, pos)[0], pos + 4
        out = []
        for _ in range(count):
            value, pos = decode(ty["vec"], raw, pos)
            out.append(value)
        return out, pos
    if "option" in ty:
        return (None, pos + 1) if raw[pos] == 0 else decode(ty["option"], raw, pos + 1)
    if "defined" in ty:
        spec = TYPES[ty["defined"]["name"]]
        if spec["kind"] == "enum":
            variant = spec["variants"][raw[pos]]
            if variant.get("fields"):
                raise ValueError(f"enum variant with fields not supported: {variant['name']}")
            return variant["name"], pos + 1
        out = {}
        for field in spec["fields"]:
            out[field["name"]], pos = decode(field["type"], raw, pos)
        return out, pos
    raise ValueError(f"unsupported IDL type {ty!r}")


def decode_account(name, raw):
    if raw[:8] != DISCRIMINATOR[name]:
        raise ValueError(f"not a {name} account")
    return decode({"defined": {"name": name}}, raw, 8)[0]


def field_offset(struct_name, field_name):
    """Byte offset of a field after the 8-byte discriminator; fields before it must be fixed size."""
    pos = 8
    for field in TYPES[struct_name]["fields"]:
        if field["name"] == field_name:
            return pos
        pos += FIXED[field["type"]]
    raise KeyError(field_name)


def collect(mint, result, args=None):
    url = config()["PASSPORT_RPC_URL"] or DEVNET_RPC
    cluster = "devnet" if url == DEVNET_RPC else "custom RPC (PASSPORT_RPC_URL)"
    result.source(f"Solana RPC ({cluster})", url)
    found = rpc("getProgramAccounts", [PROGRAM, {"encoding": "base64", "filters": [
        {"memcmp": {"offset": 0, "bytes": b58encode(DISCRIMINATOR["Endorsement"])}},
        {"memcmp": {"offset": field_offset("Endorsement", "mint"), "bytes": mint}},
    ]}], url)
    endorsements = [decode_account("Endorsement", account_bytes(a["account"])) for a in found]
    passports = accounts([e["passport"] for e in endorsements], url) if endorsements else {}

    now = time.time()
    records = []
    for e in endorsements:
        row = {"status": e["status"].lower(), "artist_id": None, "passport_age_days": None,
               "passport_revoked": None, "status_updated_at": iso(e["updated_at"]), "passport": e["passport"]}
        try:
            p = decode_account("Passport", account_bytes(passports.get(e["passport"])))
            row.update(artist_id=p["artist_id"], passport_age_days=round((now - p["issued_at"]) / 86400, 1),
                       passport_revoked=p["revoked"], passport_issued_at=iso(p["issued_at"]),
                       passport_wallet=p["wallet"], proofs=sorted({x["kind"] for x in p["proofs"]}))
        except (ValueError, IndexError, struct.error):
            result.miss(f"passport {e['passport']}", "account missing or not readable with the published IDL")
        records.append(row)

    endorsed = sum(r["status"] == "endorsed" for r in records)
    disavowed = sum(r["status"] == "disavowed" for r in records)
    result["data"] = {
        "status": "endorsed" if endorsed and not disavowed else "disavowed" if disavowed and not endorsed
        else "mixed" if records else "no record",
        "endorsed_by": endorsed,
        "disavowed_by": disavowed,
        "cluster": cluster,
        "passport_program": PROGRAM,
        "records": records,
    }
    if url == DEVNET_RPC:
        result.miss("mainnet records", "the Artist Passport program is on devnet only; these are devnet records",
                    partial=False)


if __name__ == "__main__":
    script(__doc__, collect)
