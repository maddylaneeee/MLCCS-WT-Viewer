from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import luncher


class LuncherTests(unittest.TestCase):
    def test_resolve_project_dir_prefers_named_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            extract_root = Path(temp_dir)
            project_dir = extract_root / luncher.PROJECT_DIR_NAME
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / luncher.BUILD_SCRIPT_NAME).write_text("echo test", encoding="utf-8")

            resolved = luncher._resolve_project_dir(extract_root)

        self.assertEqual(resolved, project_dir)

    def test_resolve_main_executable_uses_expected_layout(self) -> None:
        base = Path("C:/test/MLCCS-wt-viewer")
        expected = base / "dist" / luncher.APP_NAME / f"{luncher.APP_NAME}.exe"
        self.assertEqual(luncher._resolve_main_executable(base), expected)


if __name__ == "__main__":
    unittest.main()
