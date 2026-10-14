"""Offline tests for parsing, using saved responses in tests/fixtures/.
Run: python3 -m unittest discover tests"""

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "skills" / "solana-token-intel" / "scripts"))

import common  # noqa: E402
import endorsement  # noqa: E402
import history  # noqa: E402
import holders  # noqa: E402
import origin  # noqa: E402
import overview  # noqa: E402
import pools  # noqa: E402
import risk  # noqa: E402

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def fixture(name):
    return json.loads((HERE / "fixtures" / name).read_text())


def account(name, index=None):
    value = fixture(name)["result"]["value"]
    return value[index] if index is not None else value


class Base58AndPda(unittest.TestCase):
    def test_roundtrip(self):
        for addr in (USDC, common.SYSTEM_PROGRAM, common.BURN_ADDRESS):
            self.assertEqual(common.b58encode(common.b58decode(addr)), addr)

    def test_pubkey_rejects_bad_input(self):
        for bad in ("", "notamint", "0OIl" * 11, USDC + "x"):
            with self.assertRaises(ValueError):
                common.pubkey(bad)

    def test_metaplex_pda(self):
        pda = common.find_pda([b"metadata", common.b58decode(common.METAPLEX), common.b58decode(USDC)],
                              common.METAPLEX)
        self.assertEqual(pda, fixture("metaplex_usdc.json")["pda"])
        self.assertIsNotNone(account("metaplex_usdc.json"))  # the derived account exists on chain

    def test_endorsement_pda_matches_devnet_account(self):
        pda = common.find_pda([b"endorse", common.b58decode("ErafhESwQX4Mxv3oa96R6gnrp6yFBFucnyDWLNhxmXfP"),
                               common.b58decode("DffTqQTB8YsqFMA5gewV7NPau3NRxHj8AsqAGR77UWGt")],
                              endorsement.PROGRAM)
        self.assertEqual(pda, "AumZJLNZ3B4KcpP7YGWwkyh4PCuqgdBK6wtpGrFnNHmP")

    def test_wallets_are_on_curve(self):
        self.assertTrue(common.on_curve(common.b58decode("DcuQRK8UoqCAEVfKeTx9zNNKv9LwSJFXNkjjKiU7jjDv")))
        self.assertFalse(common.on_curve(common.b58decode("AumZJLNZ3B4KcpP7YGWwkyh4PCuqgdBK6wtpGrFnNHmP")))


class Overview(unittest.TestCase):
    def test_spl_mint(self):
        base, ext = overview.parse_mint(common.account_bytes(account("mint_usdc.json")))
        self.assertEqual(base["decimals"], 6)
        self.assertEqual(base["mint_authority"], "BJE5MMbqXjVwjAF7oxwPYXnTXDyspzZyt4vwenNw5ruG")
        self.assertEqual(base["freeze_authority"], "7dGbd2QZcCKcTndnHcTL8q7SMVXAkp688NTQYwrRCrar")
        self.assertEqual(ext, [])

    def test_token2022_extensions(self):
        base, ext = overview.parse_mint(common.account_bytes(account("mint_pyusd_token2022.json")))
        names = [e["name"] for e in ext]
        for expected in ("PermanentDelegate", "TransferHook", "TransferFeeConfig", "MetadataPointer"):
            self.assertIn(expected, names)

    def test_token2022_inline_metadata(self):
        base, ext = overview.parse_mint(common.account_bytes(account("mint_pump_new.json")))
        meta = next(e["metadata"] for e in ext if "metadata" in e)
        self.assertEqual((meta["name"], meta["symbol"]), ("READ", "CyberAxe"))
        self.assertIsNone(base["mint_authority"])
        self.assertFalse(meta["is_mutable"])

    def test_metaplex_metadata(self):
        meta = overview.parse_metaplex(common.account_bytes(account("metaplex_usdc.json")))
        self.assertEqual((meta["name"], meta["symbol"]), ("USD Coin", "USDC"))

    def test_ui_amount(self):
        self.assertEqual(overview.ui_amount(1000000000000000, 6), "1000000000")
        self.assertEqual(overview.ui_amount(5, 6), "0.000005")
        self.assertEqual(overview.ui_amount(7899587762636342, 6), "7899587762.636342")


class Pools(unittest.TestCase):
    EXPECTED_LP = {
        "pool_ammv4.json": "8HoQnePLqPj4M7PUDzfw8e3Ymdwgc7NLGnaTUapubyvu",
        "pool_cpmm.json": "HHAi5kits2CSTnrokkvvRxsgsGgbGjMq4EhfzBtJAUmT",
        "pool_dyn.json": "GmvE2MmN1eExdZbGq9Zu8cXwqbqPLNjgZjHD8hAiKh8d",
        "pool_pumpswap.json": "8rG18DpJB6SV8sa5B6ryHCBu5RRVPjBuLhejt83vnBFp",
    }

    def test_lp_mint_offsets(self):
        for name, lp in self.EXPECTED_LP.items():
            acc = account(name)
            off = pools.LP_MINT_OFFSET[acc["owner"]]
            self.assertEqual(common.b58encode(common.account_bytes(acc)[off:off + 32]), lp, name)

    def test_collect_with_dexscreener_fixture(self):
        pairs = fixture("dexscreener_pairs_libra.json")
        pool_accounts = {"DywR4cjNLhPy1dV9tBShpCbXoAAq3LN3Wajj9Gw64co9": account("pool_cpmm.json"),
                         "CeubWwtcmVctX47UWLmVZJ9zENtC5tdBecfE6sb4gU7k": account("pool_dyn.json")}
        lp_mint = {"data": {"parsed": {"type": "mint", "info": {"supply": "0", "decimals": 9}}}}

        def fake_accounts(addresses, url=None, encoding="base64"):
            return {a: (lp_mint if encoding == "jsonParsed" else pool_accounts.get(a)) for a in addresses}

        result = common.Result("pools", "Bo9jh3wsmcC2AjakLWzNmKJ3SgtZmXEcSaW7L2FAvUsU")
        with mock.patch.object(pools, "http_json", return_value=pairs), \
                mock.patch.object(pools, "accounts", side_effect=fake_accounts):
            pools.collect(result["mint"], result)
        rows = result["data"]["pools"]
        self.assertEqual(rows[0]["program"], "Raydium CPMM")
        self.assertEqual(rows[0]["lp_note"], "all burned (supply 0)")
        self.assertEqual(rows[1]["lp_model"], "unknown")  # orca account not in the fixture
        self.assertEqual(result["data"]["pool_count"], len(pairs))


class History(unittest.TestCase):
    def test_gecko_candles_are_oldest_first(self):
        with mock.patch.object(history, "http_json", return_value=fixture("gecko_ohlcv.json")):
            candles = history.from_gecko("pool", USDC, "4h", 5)
        times = [c["time"] for c in candles]
        self.assertEqual(times, sorted(times))
        self.assertEqual(set(candles[0]), {"time", "open", "high", "low", "close", "volume"})


class Origin(unittest.TestCase):
    def test_creation_tx(self):
        tx = fixture("tx_pump_create.json")["result"]
        with mock.patch.object(origin, "rpc", return_value=tx):
            found = origin.from_rpc("sig")
        self.assertEqual(found["creator"], "DcuQRK8UoqCAEVfKeTx9zNNKv9LwSJFXNkjjKiU7jjDv")
        self.assertIn("6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P", found["programs"])

    def test_paging_stops_at_cap(self):
        page = [{"signature": f"s{i}", "err": None, "blockTime": i} for i in range(origin.PAGE)]
        with mock.patch.object(origin, "rpc", return_value=page):
            oldest, complete, scanned = origin.oldest_signature("mint", 2)
        self.assertFalse(complete)
        self.assertEqual(scanned, 2 * origin.PAGE)


class Endorsement(unittest.TestCase):
    def test_decode_accounts(self):
        endorse, passport = account("passport_devnet.json")
        e = endorsement.decode_account("Endorsement", common.account_bytes(endorse))
        p = endorsement.decode_account("Passport", common.account_bytes(passport))
        self.assertEqual(e["mint"], "DffTqQTB8YsqFMA5gewV7NPau3NRxHj8AsqAGR77UWGt")
        self.assertEqual(e["status"], "Endorsed")
        self.assertEqual(p["artist_id"], "spotify:0RiffPassportDemo00001")
        self.assertFalse(p["revoked"])

    def test_mint_offset_from_idl(self):
        self.assertEqual(endorsement.field_offset("Endorsement", "mint"), 40)

    def test_wrong_discriminator(self):
        with self.assertRaises(ValueError):
            endorsement.decode_account("Passport", b"\0" * 100)


class Holders(unittest.TestCase):
    def test_labels_and_shares(self):
        wallet, pda = "DcuQRK8UoqCAEVfKeTx9zNNKv9LwSJFXNkjjKiU7jjDv", "AumZJLNZ3B4KcpP7YGWwkyh4PCuqgdBK6wtpGrFnNHmP"
        largest = [{"address": "ta1", "amount": "600", "uiAmountString": "600"},
                   {"address": "ta2", "amount": "400", "uiAmountString": "400"}]
        replies = {"getTokenLargestAccounts": {"value": largest},
                   "getTokenSupply": {"value": {"amount": "1000", "uiAmountString": "1000"}}}
        owners = {"ta1": pda, "ta2": wallet}

        def fake_accounts(addresses, url=None, encoding="base64"):
            if encoding == "jsonParsed":
                return {a: {"data": {"parsed": {"info": {"owner": owners[a]}}}} for a in addresses}
            return {pda: {"owner": "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA", "executable": False},
                    wallet: {"owner": common.SYSTEM_PROGRAM, "executable": False}}

        result = common.Result("holders", USDC)
        with mock.patch.object(holders, "rpc", side_effect=lambda m, p, **k: replies[m]), \
                mock.patch.object(holders, "accounts", side_effect=fake_accounts), \
                mock.patch.object(holders, "http_json", side_effect=common.SourceError("offline")):
            holders.collect(USDC, result)
        rows = result["data"]["holders"]
        self.assertEqual((rows[0]["owner_kind"], rows[0]["program"]), ("program account", "PumpSwap"))
        self.assertEqual(rows[1]["owner_kind"], "wallet")
        self.assertEqual(result["data"]["summary"]["top10_wallets_share_pct"], 40.0)


class Risk(unittest.TestCase):
    def test_extension_signal_on_pyusd(self):
        base, ext = overview.parse_mint(common.account_bytes(account("mint_pyusd_token2022.json")))
        sig = risk.extension_signal({"token_program": "Token-2022", "extensions": ext})
        self.assertEqual(sig["status"], "found")
        self.assertIn("PermanentDelegate", sig["evidence"])

    def test_authority_signals(self):
        sigs = risk.authority_signals({"mint_authority": None, "freeze_authority": "abc"})
        self.assertEqual([s["status"] for s in sigs], ["not found", "found"])

    def test_creator_signal(self):
        od = {"created_at": "2026-10-14T12:00:00Z", "creator": "c", "creator_prior_tx_count": 3,
              "creator_prior_tx_count_capped": False, "creator_first_seen": "2026-10-14T10:00:00Z"}
        self.assertEqual(risk.creator_signal(od)["status"], "found")
        od["creator_first_seen"] = "2026-10-01T10:00:00Z"
        self.assertEqual(risk.creator_signal(od)["status"], "not found")
        self.assertEqual(risk.creator_signal({"created_at": None})["status"], "not checked")

    def test_liquidity_signal(self):
        row = {"dex": "pumpswap", "pair": "A/SOL", "pool": "p", "lp_model": "LP token",
               "lp_note": None, "lp_at_burn_address_pct": 12.0, "largest_lp_holder": "w", "largest_lp_holder_pct": 88.0}
        self.assertEqual(risk.liquidity_signal({"pools": [row]})["status"], "found")
        row["lp_at_burn_address_pct"] = 99.0
        self.assertEqual(risk.liquidity_signal({"pools": [row]})["status"], "not found")
        row["lp_model"] = "positions"
        self.assertEqual(risk.liquidity_signal({"pools": [row]})["status"], "not applicable")

    def test_wording_has_no_advice(self):
        text = (HERE.parent / "skills" / "solana-token-intel" / "scripts" / "risk.py").read_text().lower()
        for word in ('"safe', "scam", "buy", "sell", "legit"):
            self.assertNotIn(word, text)


class Output(unittest.TestCase):
    def test_redaction(self):
        with mock.patch.object(common, "config", return_value={"HELIUS_API_KEY": "SECRETKEY123"}):
            text = common.redact("https://x.io/v0?api-key=SECRETKEY123&limit=1 and SECRETKEY123")
        self.assertNotIn("SECRETKEY123", text)
        self.assertEqual(common.redact("https://a.io/?api_key=abc123"), "https://a.io/?api_key=***")

    def test_retry_after_zero_still_backs_off(self):
        self.assertEqual(common._retry_after("0", 0), 2)
        self.assertEqual(common._retry_after(None, 3), 16)
        self.assertEqual(common._retry_after("120", 0), 30)

    def test_host_hides_query(self):
        self.assertEqual(common.host("https://mainnet.helius-rpc.com/?api-key=abc"), "https://mainnet.helius-rpc.com")

    def test_pretty_view_renders(self):
        result = common.Result("risk", USDC)
        result["data"] = {"signals": [risk.signal("x", "Label", "found", "evidence")],
                          "facts": {"name": "USD Coin"}, "candles": [{"time": "t", "close": 1.0}, {"time": "u", "close": 2.0}]}
        result.miss("thing", "reason")
        out = io.StringIO()
        with redirect_stdout(out):
            common.render(result)
        self.assertIn("Label", out.getvalue())
        self.assertIn("reason", out.getvalue())


if __name__ == "__main__":
    unittest.main()
