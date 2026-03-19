from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from wt_model_viewer import bootstrap, runtime_paths


class _FakeResponse:
    def __init__(self, content: bytes) -> None:
        self.content = content

    def raise_for_status(self) -> None:
        return None


class _FakeSession:
    def __init__(self, payloads: dict[str, bytes]) -> None:
        self.payloads = payloads
        self.calls: list[str] = []

    def get(self, url: str, timeout: int = 30) -> _FakeResponse:
        self.calls.append(url)
        return _FakeResponse(self.payloads[url])


class BootstrapTests(unittest.TestCase):
    def test_missing_runtime_files_returns_only_unresolved_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            overlay_root = Path(temp_dir) / "overlay"
            bundled_root = Path(temp_dir) / "bundle"
            bundled_file = bundled_root / "vendor" / "dae_runtime" / "lib" / "dae_intrinsics.dll"
            bundled_file.parent.mkdir(parents=True, exist_ok=True)
            bundled_file.write_bytes(b"ok")

            files = (
                bootstrap.RuntimeFile("vendor/dae_runtime/lib/dae_intrinsics.dll"),
                bootstrap.RuntimeFile("vendor/dae_runtime/lib/fmodL.dll"),
            )

            with patch("wt_model_viewer.bootstrap.runtime_overlay_root", return_value=overlay_root), patch(
                "wt_model_viewer.bootstrap.project_root", return_value=bundled_root
            ):
                missing = bootstrap.missing_runtime_files(files)

            self.assertEqual([entry.relative_path for entry in missing], ["vendor/dae_runtime/lib/fmodL.dll"])

    def test_ensure_runtime_files_downloads_missing_entries_to_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            overlay_root = Path(temp_dir) / "overlay"
            bundle_root = Path(temp_dir) / "bundle"
            files = (
                bootstrap.RuntimeFile("vendor/dae_runtime/lib/dae_intrinsics.dll"),
                bootstrap.RuntimeFile("vendor/dae_runtime/util/misc.py"),
            )
            session = _FakeSession(
                {
                    bootstrap.raw_file_url(files[0].relative_path): b"dll-bytes",
                    bootstrap.raw_file_url(files[1].relative_path): b"python-bytes",
                }
            )
            progress_events: list[tuple[int, int, str]] = []

            with patch("wt_model_viewer.bootstrap.runtime_overlay_root", return_value=overlay_root), patch(
                "wt_model_viewer.bootstrap.project_root", return_value=bundle_root
            ):
                written = bootstrap.ensure_runtime_files(
                    progress=lambda current, total, name: progress_events.append((current, total, name)),
                    files=files,
                    session=session,
                )

            self.assertEqual(len(written), 2)
            self.assertEqual(progress_events[0], (1, 2, files[0].relative_path))
            self.assertEqual(progress_events[1], (2, 2, files[1].relative_path))
            self.assertEqual((overlay_root / files[0].relative_path).read_bytes(), b"dll-bytes")
            self.assertEqual((overlay_root / files[1].relative_path).read_bytes(), b"python-bytes")

    def test_vendor_root_prefers_complete_overlay_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            overlay_vendor = Path(temp_dir) / runtime_paths.DEFAULT_APP_NAME / "runtime" / "vendor" / "dae_runtime"
            for relative_path in (
                "parse/dbld.py",
                "util/misc.py",
                "lib/dae_intrinsics.dll",
                "lib/daKernel-dev.dll",
                "lib/fmodL.dll",
            ):
                target = overlay_vendor / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"x")

            with patch.dict(
                os.environ,
                {"LOCALAPPDATA": temp_dir, "WT_MODEL_VIEWER_ENABLE_RUNTIME_BOOTSTRAP": "1"},
                clear=False,
            ):
                resolved = runtime_paths.vendor_root()

            self.assertEqual(resolved, overlay_vendor)

    def test_vendor_root_ignores_overlay_when_bootstrap_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            overlay_vendor = Path(temp_dir) / runtime_paths.DEFAULT_APP_NAME / "runtime" / "vendor" / "dae_runtime"
            for relative_path in (
                "parse/dbld.py",
                "util/misc.py",
                "lib/dae_intrinsics.dll",
                "lib/daKernel-dev.dll",
                "lib/fmodL.dll",
            ):
                target = overlay_vendor / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b"x")

            with patch.dict(os.environ, {"LOCALAPPDATA": temp_dir}, clear=False):
                resolved = runtime_paths.vendor_root()

            self.assertNotEqual(resolved, overlay_vendor)


if __name__ == "__main__":
    unittest.main()
