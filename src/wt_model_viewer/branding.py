from __future__ import annotations

import shutil
from pathlib import Path

import requests

from .runtime_paths import asset_path, local_cache_root as runtime_local_cache_root


APP_NAME = "MLCCS-wt-viewer"
ICON_FILE_NAME = "MLCCS.ico"
ICON_URL = "https://lixinchen.ca/weblogo/MLCCS.ico"


def local_cache_root() -> Path:
    return runtime_local_cache_root(APP_NAME)


def cached_icon_path() -> Path:
    return local_cache_root() / "cache" / ICON_FILE_NAME


def bundled_icon_path() -> Path:
    return asset_path(ICON_FILE_NAME)


def current_icon_path() -> Path | None:
    for candidate in (cached_icon_path(), bundled_icon_path()):
        if candidate.exists() and candidate.stat().st_size > 0:
            return candidate
    return None


def fetch_and_cache_icon() -> Path | None:
    cache_path = cached_icon_path()
    if cache_path.exists() and cache_path.stat().st_size > 0:
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        response = requests.get(ICON_URL, timeout=15)
        response.raise_for_status()
        if not response.content:
            raise ValueError("Downloaded icon is empty")
        cache_path.write_bytes(response.content)
        return cache_path
    except Exception:
        bundled_path = bundled_icon_path()
        if bundled_path.exists() and bundled_path.stat().st_size > 0:
            shutil.copyfile(bundled_path, cache_path)
            return cache_path
        return None
