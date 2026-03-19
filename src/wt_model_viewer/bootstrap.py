from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

import requests

from .runtime_paths import bundle_root, project_root, runtime_overlay_root

REPO_RAW_BASE_URL = "https://raw.githubusercontent.com/maddylaneeee/MLCCS-WT-Viewer/main/"


@dataclass(frozen=True, slots=True)
class RuntimeFile:
    relative_path: str


REQUIRED_RUNTIME_FILES: tuple[RuntimeFile, ...] = (
    RuntimeFile("vendor/dae_runtime/lib/dae_intrinsics.dll"),
    RuntimeFile("vendor/dae_runtime/lib/daKernel-dev.dll"),
    RuntimeFile("vendor/dae_runtime/lib/fmodL.dll"),
    RuntimeFile("vendor/dae_runtime/parse/datablock.py"),
    RuntimeFile("vendor/dae_runtime/parse/dbld.py"),
    RuntimeFile("vendor/dae_runtime/parse/gameres.py"),
    RuntimeFile("vendor/dae_runtime/parse/material.py"),
    RuntimeFile("vendor/dae_runtime/parse/mesh.py"),
    RuntimeFile("vendor/dae_runtime/parse/realres.py"),
    RuntimeFile("vendor/dae_runtime/util/assetcacher.py"),
    RuntimeFile("vendor/dae_runtime/util/assetmanager.py"),
    RuntimeFile("vendor/dae_runtime/util/decompression.py"),
    RuntimeFile("vendor/dae_runtime/util/enums.py"),
    RuntimeFile("vendor/dae_runtime/util/fileread.py"),
    RuntimeFile("vendor/dae_runtime/util/log.py"),
    RuntimeFile("vendor/dae_runtime/util/misc.py"),
    RuntimeFile("vendor/dae_runtime/util/settings.py"),
    RuntimeFile("vendor/dae_runtime/util/terminable.py"),
)


def overlay_runtime_path(relative_path: str) -> Path:
    return runtime_overlay_root() / Path(relative_path)


def bundled_runtime_path(relative_path: str) -> Path:
    relative = Path(relative_path)
    if relative.parts and relative.parts[0] == "vendor":
        if getattr(sys, "frozen", False):
            return bundle_root() / relative
        return project_root() / relative
    return bundle_root() / relative


def raw_file_url(relative_path: str) -> str:
    base_url = os.environ.get("WT_MODEL_VIEWER_RUNTIME_BASE_URL", REPO_RAW_BASE_URL).strip()
    if not base_url:
        base_url = REPO_RAW_BASE_URL
    return base_url.rstrip("/") + "/" + relative_path.replace("\\", "/")


def is_valid_file(path: Path) -> bool:
    return path.exists() and path.stat().st_size > 0


def resolve_runtime_path(relative_path: str) -> Path | None:
    for candidate in (overlay_runtime_path(relative_path), bundled_runtime_path(relative_path)):
        if is_valid_file(candidate):
            return candidate
    return None


def missing_runtime_files(files: Iterable[RuntimeFile] | None = None) -> list[RuntimeFile]:
    manifest = tuple(files or REQUIRED_RUNTIME_FILES)
    return [entry for entry in manifest if resolve_runtime_path(entry.relative_path) is None]


def ensure_runtime_files(
    progress: Callable[[int, int, str], None] | None = None,
    files: Iterable[RuntimeFile] | None = None,
    session: requests.Session | None = None,
) -> list[Path]:
    manifest = tuple(files or REQUIRED_RUNTIME_FILES)
    missing = missing_runtime_files(manifest)
    if not missing:
        return []

    client = session or requests.Session()
    downloaded: list[Path] = []

    for index, entry in enumerate(missing, start=1):
        if progress is not None:
            progress(index, len(missing), entry.relative_path)

        file_url = raw_file_url(entry.relative_path)
        response = client.get(file_url, timeout=30)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"Runtime file not available at download source: {entry.relative_path}") from exc
        if not response.content:
            raise ValueError(f"Downloaded file is empty: {entry.relative_path}")

        target = overlay_runtime_path(entry.relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(response.content)
        downloaded.append(target)

    return downloaded
