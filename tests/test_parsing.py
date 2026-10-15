"""Offline tests for parsing, using saved responses in tests/fixtures/.
Run: python3 -m unittest discover tests"""

import io
import json
import tempfile
import time
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

import common  # noqa: E402
import creator  # noqa: E402
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

    def test_wallets_are_on_curve(self):
        self.assertTrue(common.on_curve(common.b58decode("DcuQRK8UoqCAEVfKeTx9zNNKv9LwSJFXNkjjKiU7jjDv")))
        self.assertFalse(common.on_curve(common.b58decode(fixture("metaplex_usdc.json")["pda"])))


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
        text = (HERE.parent / "scripts" / "risk.py").read_text().lower()
        for word in ('"safe', "scam", "buy", "sell", "legit"):
            self.assertNotIn(word, text)


class Creator(unittest.TestCase):
    MINT, WALLET, CURVE = ("3apEwET6mR5ZS7ypiPJuaRYBYzvort8vqfaSgmjupump", "B3ZSJaxg3fmrZJaphu5D1PjzMJH9dKP25AJNjgY3uzTv",
                           "3v4PDEHuPiZp8Msv2Xnw5aLBEwhUgmFPsTjVPc3GvJ6Q")

    def test_created_mint_skips_route_token(self):
        tx = fixture("helius_create_router.json")[0]  # bought through another token (DOPE) in the same tx
        self.assertEqual(creator.created_mint(tx), self.MINT)

    def test_repeated_mint_listed_once_with_oldest_date(self):
        tx = fixture("helius_create_router.json")[0]
        later = dict(tx, timestamp=tx["timestamp"] + 60, source="STREAMFLOW_TIMELOCK")
        with mock.patch.object(creator, "http_json", side_effect=[[later, tx], []]):
            coins = creator.creator_coins(self.WALLET, "k", common.Result("creator", self.MINT))
        self.assertEqual([(c["mint"], c["helius_source"]) for c in coins], [(self.MINT, "PUMP_FUN")])

    def test_empty_search_window_continues(self):
        sig = "4" * 88
        empty = common.SourceError("HTTP 404", 404, '{"error":"Failed to find events within the search period. To '
                                   f'continue search, query the API again with the `before-signature` parameter set to {sig}."}}')
        calls = []
        replies = iter([empty, fixture("helius_create_router.json"), []])

        def fake(url):
            calls.append(url)
            reply = next(replies)
            if isinstance(reply, Exception):
                raise reply
            return reply
        with mock.patch.object(creator, "http_json", side_effect=fake):
            coins = creator.creator_coins(self.WALLET, "k", common.Result("creator", self.MINT))
        self.assertIn(f"before-signature={sig}", calls[1])
        self.assertEqual([c["mint"] for c in coins], [self.MINT])

    def test_moves_to_a_pool_are_labelled(self):
        with mock.patch.object(creator, "http_json", return_value=fixture("helius_creator_moves.json")):
            moves, done, _ = creator.creator_moves(self.MINT, self.WALLET, 0, {self.CURVE}, "k",
                                                   common.Result("creator", self.MINT))
        self.assertTrue(done)
        self.assertEqual([m["kind"] for m in moves], ["received"] + ["sent to pool"] * 5)
        self.assertEqual(creator.move_kind(True, "TRANSFER", "elsewhere", {self.CURVE}), "sent")
        self.assertEqual(creator.move_kind(True, "SWAP", self.CURVE, {self.CURVE}), "sold")


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


class Safety(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        patches = [mock.patch.object(common, "USAGE_FILE", Path(self.tmp.name) / "usage.json"),
                   mock.patch.object(common, "_run_calls", 0),
                   mock.patch.object(common, "config", return_value={"MINT_MAX_CALLS_PER_HOUR": "3"}),
                   mock.patch.object(common.time, "sleep")]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        self.addCleanup(self.tmp.cleanup)

    def test_hourly_budget_refuses_and_is_shared(self):
        for _ in range(3):
            common.spend("https://api.geckoterminal.com/x")
        with self.assertRaises(common.SourceError) as e:
            common.spend("https://api.geckoterminal.com/y")
        self.assertEqual(e.exception.status, "budget")
        common.spend("https://api.dexscreener.com/z")  # other sources have their own budget
        self.assertEqual(len(common.usage()["api.geckoterminal.com"]), 3)

    def test_old_requests_expire(self):
        common.USAGE_FILE.write_text(json.dumps({"a.io": [time.time() - 3700] * 5}))
        common.spend("https://a.io/")
        self.assertEqual(len(common.usage()["a.io"]), 1)

    def test_run_cap(self):
        with mock.patch.object(common, "_run_calls", common.RUN_CAP):
            with self.assertRaises(common.SourceError):
                common.spend("https://b.io/")

    def test_rpc_attempts_are_bounded(self):
        calls = []

        def limited(*a, **k):
            calls.append(1)
            raise common.SourceError("HTTP 429", 429)

        with mock.patch.object(common, "http_json", side_effect=limited):
            with self.assertRaises(common.SourceError):
                common.rpc("getSlot", [], "https://rpc.example", retries=4)
        self.assertEqual(len(calls), 5)

    def test_budget_errors_are_not_retried(self):
        calls = []

        def refused(*a, **k):
            calls.append(1)
            raise common.SourceError("budget used up", "budget")

        with mock.patch.object(common, "http_json", side_effect=refused):
            with self.assertRaises(common.SourceError):
                common.rpc("getSlot", [], "https://rpc.example")
        self.assertEqual(len(calls), 1)


class FullHistory(unittest.TestCase):
    def test_covers_launch(self):
        self.assertTrue(history.covers_launch("2026-10-14T21:00:00Z", "2026-10-14T21:30:24Z", "1h"))
        self.assertFalse(history.covers_launch("2026-04-07T00:00:00Z", "2025-02-14T22:02:29Z", "1d"))
        self.assertIsNone(history.covers_launch("2026-04-07T00:00:00Z", None, "1d"))


class Launcher(unittest.TestCase):
    def test_help_and_unknown_command(self):
        import subprocess
        mint = HERE.parent / "bin" / "mint"
        ok = subprocess.run([sys.executable, str(mint), "help"], capture_output=True, text=True)
        self.assertEqual(ok.returncode, 0)
        self.assertIn("mint risk <mint>", ok.stdout)
        bad = subprocess.run([sys.executable, str(mint), "nope"], capture_output=True, text=True)
        self.assertEqual(bad.returncode, 2)


if __name__ == "__main__":
    unittest.main()
