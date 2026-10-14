#!/usr/bin/env python3
"""Mint account facts: supply, decimals, authorities, token program,
Token-2022 extensions and metadata."""

import struct

from common import (METAPLEX, SPL_TOKEN, TOKEN_2022, account_bytes, accounts, b58decode,
                    b58encode, find_pda, rpc_url, script)

# Token-2022 extension type numbers, in order (spl-token-2022 ExtensionType).
EXTENSIONS = [
    "Uninitialized", "TransferFeeConfig", "TransferFeeAmount", "MintCloseAuthority",
    "ConfidentialTransferMint", "ConfidentialTransferAccount", "DefaultAccountState",
    "ImmutableOwner", "MemoTransfer", "NonTransferable", "InterestBearingConfig", "CpiGuard",
    "PermanentDelegate", "NonTransferableAccount", "TransferHook", "TransferHookAccount",
    "ConfidentialTransferFeeConfig", "ConfidentialTransferFeeAmount", "MetadataPointer",
    "TokenMetadata", "GroupPointer", "TokenGroup", "GroupMemberPointer", "TokenGroupMember",
    "ConfidentialMintBurn", "ScaledUiAmount", "Pausable", "PausableAccount",
]


def optional_key(raw):
    return b58encode(raw) if any(raw) else None


def ui_amount(raw_amount, decimals):
    text = str(raw_amount).rjust(decimals + 1, "0")
    whole, frac = text[:len(text) - decimals], text[len(text) - decimals:].rstrip("0")
    return f"{whole}.{frac}" if frac else whole


def borsh_str(raw, pos):
    size = struct.unpack_from("<I", raw, pos)[0]
    return raw[pos + 4:pos + 4 + size].decode("utf-8", "replace").rstrip("\0").strip(), pos + 4 + size


def parse_mint(raw):
    """Base mint (82 bytes) plus any Token-2022 TLV extensions after byte 165."""
    coption = lambda off: b58encode(raw[off + 4:off + 36]) if raw[off] == 1 else None
    mint = {
        "supply_raw": struct.unpack_from("<Q", raw, 36)[0],
        "decimals": raw[44],
        "mint_authority": coption(0),
        "freeze_authority": coption(46),
    }
    extensions = []
    if len(raw) > 166 and raw[165] == 1:  # account type 1 = mint
        pos = 166
        while pos + 4 <= len(raw):
            kind, size = struct.unpack_from("<HH", raw, pos)
            if kind == 0:
                break
            extensions.append(describe_extension(kind, raw[pos + 4:pos + 4 + size]))
            pos += 4 + size
    return mint, extensions


def describe_extension(kind, v):
    name = EXTENSIONS[kind] if kind < len(EXTENSIONS) else f"Unknown({kind})"
    ext = {"name": name}
    if name == "TransferFeeConfig":
        ext.update(authority=optional_key(v[0:32]), fee_basis_points=struct.unpack_from("<H", v, 106)[0],
                   max_fee_raw=struct.unpack_from("<Q", v, 98)[0])
    elif name in ("PermanentDelegate", "MintCloseAuthority"):
        ext["authority"] = optional_key(v[0:32])
    elif name == "TransferHook":
        ext.update(authority=optional_key(v[0:32]), hook_program=optional_key(v[32:64]))
    elif name == "DefaultAccountState":
        ext["default_state"] = {1: "initialized", 2: "frozen"}.get(v[0], str(v[0]))
    elif name == "MetadataPointer":
        ext.update(authority=optional_key(v[0:32]), metadata_address=optional_key(v[32:64]))
    elif name == "Pausable":
        ext.update(authority=optional_key(v[0:32]), paused=bool(v[32]))
    elif name == "TokenMetadata":
        ext["metadata"] = parse_token_metadata(v)
    return ext


def parse_token_metadata(v):
    """Token-2022 TokenMetadata extension: authority, mint, name, symbol, uri."""
    name, pos = borsh_str(v, 64)
    symbol, pos = borsh_str(v, pos)
    uri, pos = borsh_str(v, pos)
    authority = optional_key(v[0:32])
    return {"name": name, "symbol": symbol, "uri": uri, "update_authority": authority,
            "is_mutable": authority is not None, "source": "Token-2022 metadata extension"}


def parse_metaplex(raw):
    """Metaplex metadata account: key, update authority, mint, data, creators, flags."""
    name, pos = borsh_str(raw, 65)
    symbol, pos = borsh_str(raw, pos)
    uri, pos = borsh_str(raw, pos)
    pos += 2  # seller fee basis points
    if raw[pos] == 1:
        pos += 5 + 34 * struct.unpack_from("<I", raw, pos + 1)[0]
    else:
        pos += 1
    return {"name": name, "symbol": symbol, "uri": uri, "update_authority": b58encode(raw[1:33]),
            "is_mutable": bool(raw[pos + 1]), "source": "Metaplex metadata account"}


def collect(mint, result, args=None):
    url = rpc_url()
    metadata_pda = find_pda([b"metadata", b58decode(METAPLEX), b58decode(mint)], METAPLEX)
    found = accounts([mint, metadata_pda])
    result.source("Solana RPC", url)
    account = found[mint]
    if not account:
        raise ValueError(f"no account found at {mint}")
    if account["owner"] not in (SPL_TOKEN, TOKEN_2022) or len(account_bytes(account)) < 82:
        raise ValueError(f"{mint} is not a token mint (owner program {account['owner']})")
    base, extensions = parse_mint(account_bytes(account))
    data = {
        "token_program": "Token-2022" if account["owner"] == TOKEN_2022 else "SPL Token",
        "token_program_id": account["owner"],
        "supply": ui_amount(base["supply_raw"], base["decimals"]),
        **base,
    }
    if account["owner"] == TOKEN_2022:
        data["extensions"] = [{k: v for k, v in e.items() if k != "metadata"} for e in extensions]
    inline = next((e["metadata"] for e in extensions if "metadata" in e), None)
    if inline:
        data["metadata"] = inline
    elif found[metadata_pda]:
        data["metadata"] = parse_metaplex(account_bytes(found[metadata_pda]))
    else:
        data["metadata"] = None
        result.miss("metadata", "no Token-2022 metadata extension and no Metaplex metadata account", partial=False)
    result["data"] = data


if __name__ == "__main__":
    script(__doc__, collect)
