import os
import tempfile
import unittest
from pathlib import Path

import main


class ResolveAuthPathTests(unittest.TestCase):
    def test_prefers_oauth_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                Path("browser.json").write_text("browser", encoding="utf-8")
                Path("oauth.json").write_text("oauth", encoding="utf-8")
                resolved = main._resolve_yt_auth_path(None)
                self.assertEqual(resolved, Path("oauth.json"))
            finally:
                os.chdir(old_cwd)

    def test_uses_browser_when_only_browser_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                Path("browser.json").write_text("browser", encoding="utf-8")
                resolved = main._resolve_yt_auth_path(None)
                self.assertEqual(resolved, Path("browser.json"))
            finally:
                os.chdir(old_cwd)

    def test_respects_headers_arg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_cwd = os.getcwd()
            try:
                os.chdir(tmpdir)
                custom = Path("custom_auth.json")
                custom.write_text("custom", encoding="utf-8")
                resolved = main._resolve_yt_auth_path(str(custom))
                self.assertEqual(resolved, custom)
            finally:
                os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()
