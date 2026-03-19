from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wt_model_viewer import branding


class BrandingTests(unittest.TestCase):
    def test_fetch_and_cache_icon_reuses_existing_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_root = Path(temp_dir)
            cache_path = cache_root / branding.APP_NAME / "cache" / branding.ICON_FILE_NAME
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(b"cached-ico")

            with patch.dict(os.environ, {"LOCALAPPDATA": temp_dir}, clear=False), patch("wt_model_viewer.branding.requests.get") as get:
                resolved = branding.fetch_and_cache_icon()

            self.assertEqual(resolved, cache_path)
            self.assertEqual(cache_path.read_bytes(), b"cached-ico")
            get.assert_not_called()

    def test_fetch_and_cache_icon_falls_back_to_bundled_icon(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / branding.APP_NAME / "cache" / branding.ICON_FILE_NAME
            bundled_path = Path(temp_dir) / "bundled.ico"
            bundled_path.write_bytes(b"bundled-ico")

            with patch.dict(os.environ, {"LOCALAPPDATA": temp_dir}, clear=False), patch(
                "wt_model_viewer.branding.bundled_icon_path", return_value=bundled_path
            ), patch("wt_model_viewer.branding.requests.get", side_effect=RuntimeError("offline")):
                resolved = branding.fetch_and_cache_icon()

            self.assertEqual(resolved, cache_path)
            self.assertTrue(cache_path.exists())
            self.assertEqual(cache_path.read_bytes(), b"bundled-ico")

    def test_current_icon_path_prefers_cache_over_bundled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            cache_path = Path(temp_dir) / branding.APP_NAME / "cache" / branding.ICON_FILE_NAME
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(b"cached-ico")
            bundled_path = Path(temp_dir) / "bundled.ico"
            bundled_path.write_bytes(b"bundled-ico")

            with patch.dict(os.environ, {"LOCALAPPDATA": temp_dir}, clear=False), patch(
                "wt_model_viewer.branding.bundled_icon_path", return_value=bundled_path
            ):
                resolved = branding.current_icon_path()

            self.assertEqual(resolved, cache_path)


if __name__ == "__main__":
    unittest.main()
