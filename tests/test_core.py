import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from zapret_app import app_updater, diagnostics, fakes, hosts, paths, strategies, tester, updater  # noqa: E402
from zapret_app.theme import hex_to_rgb, rgb_to_hex  # noqa: E402


class StrategiesTest(unittest.TestCase):
    def test_strategies_loaded(self):
        items = strategies.load_all()
        self.assertGreater(len(items), 10)
        self.assertIn("general", [s["id"] for s in items])

    def test_all_placeholders_replaced_for_every_mode(self):
        for s in strategies.load_all():
            for mode in strategies.MODES:
                argv = strategies.winws_args(s["id"], mode, "1024-65535", "1024-65535")
                self.assertTrue(argv)
                for token in argv:
                    for ph in ("%BIN%", "%LISTS%", "%GameFilter"):
                        self.assertNotIn(ph, token, f"{s['id']}/{mode}: {token}")

    def test_binaries_exist(self):
        for s in strategies.load_all():
            for token in strategies.winws_args(s["id"], "all", "1024-65535", "1024-65535"):
                marker = str(paths.BIN_DIR)
                if marker in token:
                    path = token[token.index(marker):]
                    self.assertTrue(Path(path).exists(), f"{s['id']}: нет {path}")

    def test_game_ports_match_original_logic(self):
        self.assertEqual(strategies.game_ports("all", "1-2", "3-4"), ("1-2", "3-4"))
        self.assertEqual(strategies.game_ports("tcp", "1-2", "3-4"), ("1-2", "12"))
        self.assertEqual(strategies.game_ports("udp", "1-2", "3-4"), ("12", "3-4"))
        self.assertEqual(strategies.game_ports("off", "1-2", "3-4"), ("12", "12"))

    def test_valid_range(self):
        self.assertTrue(strategies.valid_range("1024-65535"))
        self.assertFalse(strategies.valid_range("70000-1"))
        self.assertFalse(strategies.valid_range("5-1"))
        self.assertFalse(strategies.valid_range("abc"))


class UpdaterTest(unittest.TestCase):
    def test_parse_version(self):
        self.assertEqual(app_updater.parse_version("v0.3.1"), (0, 3, 1))
        self.assertEqual(app_updater.parse_version("0.2.0-dev"), (0, 2, 0))
        self.assertIsNone(app_updater.parse_version("latest"))

    def test_is_newer(self):
        self.assertTrue(app_updater.is_newer("0.3.1", "0.3.0"))
        self.assertFalse(app_updater.is_newer("0.3.0", "0.3.0"))
        self.assertFalse(app_updater.is_newer("0.2.9", "0.3.0"))

    def test_pick_asset_takes_only_setup_from_own_repo(self):
        base = "https://github.com/iamplaho/zapret-app/releases/download/v0.3.1/"
        assets = [
            {"name": "zapret-app-portable-0.3.1.zip", "browser_download_url": base + "p.zip"},
            {"name": "zapret-app-setup-0.3.1.exe", "browser_download_url": base + "zapret-app-setup-0.3.1.exe"},
        ]
        self.assertEqual(app_updater.pick_asset(assets)["name"], "zapret-app-setup-0.3.1.exe")

    def test_pick_asset_rejects_foreign_domain(self):
        assets = [{"name": "zapret-app-setup-9.9.9.exe",
                   "browser_download_url": "https://evil.example.com/zapret-app-setup-9.9.9.exe"}]
        self.assertIsNone(app_updater.pick_asset(assets))


class IpsetModeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.lists = Path(self.tmp.name)
        self.patch = mock.patch.object(paths, "LISTS_DIR", self.lists)
        self.patch.start()
        (self.lists / "ipset-all.txt").write_text("1.1.1.0/24\n2.2.2.0/24\n", encoding="utf-8")

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def test_loaded_to_none_and_back_keeps_list(self):
        self.assertEqual(updater.ipset_mode(), "loaded")
        updater.set_ipset_mode("none")
        self.assertEqual(updater.ipset_mode(), "none")
        self.assertIn(updater.IPSET_PLACEHOLDER, (self.lists / "ipset-all.txt").read_text())
        self.assertIn("1.1.1.0/24", (self.lists / "ipset-all.txt.backup").read_text())
        updater.set_ipset_mode("loaded")
        self.assertEqual(updater.ipset_mode(), "loaded")
        self.assertIn("2.2.2.0/24", (self.lists / "ipset-all.txt").read_text())

    def test_any_mode_is_empty_file(self):
        updater.set_ipset_mode("any")
        self.assertEqual(updater.ipset_mode(), "any")
        self.assertEqual((self.lists / "ipset-all.txt").read_text(), "")


class HostsTest(unittest.TestCase):
    def test_only_missing_entries_are_added(self):
        current = "127.0.0.1 localhost\n0.0.0.0 discord.com\n"
        repo = "# comment\n0.0.0.0 discord.com\n0.0.0.0 youtube.com\n"
        self.assertEqual(hosts.missing_entries(current, repo), ["0.0.0.0 youtube.com"])

    def test_block_is_ascii_and_marked(self):
        block = hosts.build_block(["0.0.0.0 youtube.com"])
        self.assertIn(hosts.MARKER.encode("utf-8"), block)
        block.decode("ascii")


class FakesTest(unittest.TestCase):
    def test_list_apply_current(self):
        with tempfile.TemporaryDirectory() as tmp:
            bin_dir = Path(tmp)
            (bin_dir / "tls_a.bin").write_bytes(b"AAA")
            (bin_dir / "quic_b.bin").write_bytes(b"BBB")
            (bin_dir / "ACTIVE_DISCORD_UDP.bin").write_bytes(b"x")
            with mock.patch.object(paths, "BIN_DIR", bin_dir):
                self.assertEqual(fakes.list_fakes(), ["quic_b.bin", "tls_a.bin"])
                fakes.apply("discord", "tls_a.bin")
                self.assertEqual(fakes.current("discord"), "tls_a.bin")
                self.assertIsNone(fakes.current("game"))


class DiagnosticsTest(unittest.TestCase):
    def test_parse_services(self):
        text = ("SERVICE_NAME: BFE\nDISPLAY_NAME: Base Filtering Engine\n\n"
                "SERVICE_NAME: winws1\nDISPLAY_NAME: Winws service: x\n")
        self.assertEqual(diagnostics.parse_services(text),
                         [("BFE", "Base Filtering Engine"), ("winws1", "Winws service: x")])

    def test_proxy_and_timestamps_detection(self):
        self.assertTrue(diagnostics.proxy_enabled("    ProxyEnable    REG_DWORD    0x1"))
        self.assertFalse(diagnostics.proxy_enabled("    ProxyEnable    REG_DWORD    0x0"))
        self.assertTrue(diagnostics.tcp_timestamps_enabled("Timestamps : enabled"))
        self.assertFalse(diagnostics.tcp_timestamps_enabled("Timestamps : disabled"))


class TesterTest(unittest.TestCase):
    def test_targets_loaded(self):
        targets = tester.load_targets()
        self.assertGreater(len(targets), 20)
        self.assertIn("DiscordMain", [k for k, _ in targets])
        self.assertTrue(all(url.startswith("https://") for _, url in targets))

    def test_ping_only_targets_skipped(self):
        self.assertIsNone(tester.LINE_RE.match('Ping1 = "PING:1.2.3.4"'))
        self.assertIsNotNone(tester.LINE_RE.match('Web = "https://example.com"'))


class ThemeTest(unittest.TestCase):
    def test_color_round_trip(self):
        self.assertEqual(rgb_to_hex(hex_to_rgb("#3f3f46")), "#3f3f46")


class AssetsTest(unittest.TestCase):
    def test_icons_and_installer_present(self):
        self.assertTrue((ROOT / "assets" / "icon.ico").exists())
        self.assertTrue((ROOT / "assets" / "icon.png").exists())
        self.assertTrue((ROOT / "installer" / "zapret-app.iss").exists())


if __name__ == "__main__":
    unittest.main()
