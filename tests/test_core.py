import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from zapret_app import paths, strategies  # noqa: E402


class StrategiesTest(unittest.TestCase):
    def test_strategies_loaded(self):
        items = strategies.load_all()
        self.assertGreater(len(items), 10)
        self.assertIn("general", [s["id"] for s in items])

    def test_all_placeholders_replaced(self):
        for s in strategies.load_all():
            for game in (False, True):
                argv = strategies.build_argv(s["id"], game)
                self.assertTrue(argv)
                for token in argv:
                    for ph in ("%BIN%", "%LISTS%", "%GameFilter"):
                        self.assertNotIn(ph, token, f"{s['id']}: {token}")

    def test_binaries_exist(self):
        for s in strategies.load_all():
            for token in strategies.build_argv(s["id"], False):
                marker = str(paths.BIN_DIR)
                if marker in token:
                    path = token[token.index(marker):]
                    self.assertTrue(Path(path).exists(), f"{s['id']}: нет {path}")

    def test_game_filter_changes_ports(self):
        on = " ".join(strategies.build_argv("general", True))
        off = " ".join(strategies.build_argv("general", False))
        self.assertIn("1024-65535", on)
        self.assertNotIn("1024-65535", off)


class AssetsTest(unittest.TestCase):
    def test_icons_present(self):
        self.assertTrue((ROOT / "assets" / "icon.ico").exists())
        self.assertTrue((ROOT / "assets" / "icon.png").exists())

    def test_installer_script_present(self):
        self.assertTrue((ROOT / "installer" / "zapret-app.iss").exists())


if __name__ == "__main__":
    unittest.main()
