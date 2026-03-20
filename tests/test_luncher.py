from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import luncher


class LuncherTests(unittest.TestCase):
    def test_resolve_package_dir_prefers_named_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            extract_root = Path(temp_dir)
            install_dir = extract_root / luncher.INSTALL_DIR_NAME
            install_dir.mkdir(parents=True, exist_ok=True)
            (install_dir / luncher.MAIN_EXE_NAME).write_text("binary", encoding="utf-8")

            resolved = luncher._resolve_package_dir(extract_root)

        self.assertEqual(resolved, install_dir)

    def test_resolve_main_executable_uses_expected_layout(self) -> None:
        base = Path("C:/test/MLCCS-wt-viewer")
        expected = base / f"{luncher.APP_NAME}.exe"
        self.assertEqual(luncher._resolve_main_executable(base), expected)

    def test_resolve_package_dir_accepts_flat_root_layout(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            extract_root = Path(temp_dir)
            (extract_root / luncher.MAIN_EXE_NAME).write_text("binary", encoding="utf-8")

            resolved = luncher._resolve_package_dir(extract_root)

        self.assertEqual(resolved, extract_root)

    def test_parse_sha256_text_accepts_sha256sum_format(self) -> None:
        checksum = "a" * 64
        payload = f"{checksum}  {luncher.PACKAGE_FILE_NAME}"
        self.assertEqual(luncher._parse_sha256_text(payload), checksum)

    def test_parse_sha256_text_rejects_invalid_payload(self) -> None:
        self.assertIsNone(luncher._parse_sha256_text("not-a-checksum"))

    def test_bundled_package_path_prefers_runtime_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            runtime_dir = Path(temp_dir)
            package_path = runtime_dir / luncher.PACKAGE_FILE_NAME
            package_path.write_text("payload", encoding="utf-8")

            with mock.patch.object(luncher, "_runtime_data_dir", return_value=runtime_dir):
                self.assertEqual(luncher._bundled_package_path(), package_path)

    def test_load_checksum_from_file_reads_valid_checksum(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            checksum_path = Path(temp_dir) / f"{luncher.PACKAGE_FILE_NAME}.sha256"
            checksum = "b" * 64
            checksum_path.write_text(f"{checksum}  {luncher.PACKAGE_FILE_NAME}", encoding="utf-8")

            logs: list[str] = []
            self.assertEqual(
                luncher._load_checksum_from_file(checksum_path, logs.append, "Bundled"),
                checksum,
            )

    def test_copy_file_with_sha256_copies_bytes_and_returns_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            source = temp_path / "source.bin"
            target = temp_path / "target.bin"
            source.write_bytes(b"abc123")

            logs: list[str] = []
            digest = luncher._copy_file_with_sha256(source, target, logs.append, "Copied bundled package")

            self.assertEqual(target.read_bytes(), b"abc123")
            self.assertEqual(digest, "6ca13d52ca70c883e0f0bb101e425a89e8624de51db2d2392593af6a84118090")


if __name__ == "__main__":
    unittest.main()
