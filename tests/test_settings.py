import tempfile
import unittest
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from settings import ConfigError, load_config


CONFIG_TEXT = """\
api:
  key: test-key
  url: https://photos.buicha.jp/api
  album: Desktop
watchdog:
  directories:
    - |-
      C:\\Users\\test\\OneDrive\\画像\\VRChat
"""


class LoadConfigTests(unittest.TestCase):
    def _write_config(self, content):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "config.yaml"
        path.write_bytes(content)
        return path

    def test_loads_utf8_config_with_japanese_path(self):
        path = self._write_config(CONFIG_TEXT.encode("utf-8-sig"))

        config, encoding, _ = load_config(path)

        self.assertEqual("utf-8-sig", encoding)
        self.assertEqual(
            r"C:\Users\test\OneDrive\画像\VRChat",
            config["watchdog"]["directories"][0],
        )

    def test_loads_legacy_cp932_config_with_japanese_path(self):
        path = self._write_config(CONFIG_TEXT.encode("cp932"))

        config, encoding, _ = load_config(path)

        self.assertEqual("cp932", encoding)
        self.assertEqual(
            r"C:\Users\test\OneDrive\画像\VRChat",
            config["watchdog"]["directories"][0],
        )

    def test_rejects_missing_watch_directories(self):
        path = self._write_config(
            b"api:\n  key: test-key\n  url: https://photos.buicha.jp/api\nwatchdog:\n"
        )

        with self.assertRaises(ConfigError):
            load_config(path)


if __name__ == "__main__":
    unittest.main()
