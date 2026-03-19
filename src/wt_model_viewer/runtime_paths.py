from __future__ import annotations

import os
import sys
from pathlib import Path

DEFAULT_APP_NAME = "MLCCS-wt-viewer"
_DLL_DIRECTORY_HANDLES: list[object] = []


def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def local_cache_root(app_name: str = DEFAULT_APP_NAME) -> Path:
    base_dir = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return base_dir / app_name


def runtime_overlay_root(app_name: str = DEFAULT_APP_NAME) -> Path:
    return local_cache_root(app_name) / "runtime"


def runtime_bootstrap_enabled() -> bool:
    return os.environ.get("WT_MODEL_VIEWER_ENABLE_RUNTIME_BOOTSTRAP", "").strip() == "1"


def bundle_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).resolve().parent))

    return project_root() / "src"


def overlay_vendor_root() -> Path:
    return runtime_overlay_root() / "vendor" / "dae_runtime"


def _overlay_vendor_ready() -> bool:
    if not runtime_bootstrap_enabled():
        return False

    vendor = overlay_vendor_root()
    required = (
        vendor / "parse" / "dbld.py",
        vendor / "util" / "misc.py",
        vendor / "lib" / "dae_intrinsics.dll",
        vendor / "lib" / "daKernel-dev.dll",
        vendor / "lib" / "fmodL.dll",
    )
    return all(path.exists() and path.stat().st_size > 0 for path in required)


def vendor_root() -> Path:
    if _overlay_vendor_ready():
        return overlay_vendor_root()

    if getattr(sys, "frozen", False):
        return bundle_root() / "vendor" / "dae_runtime"

    return project_root() / "vendor" / "dae_runtime"


def asset_path(*parts: str) -> Path:
    if runtime_bootstrap_enabled():
        overlay = runtime_overlay_root() / "wt_model_viewer" / "assets" / Path(*parts)
        if overlay.exists() and overlay.stat().st_size > 0:
            return overlay

    return bundle_root() / "wt_model_viewer" / "assets" / Path(*parts)


def bootstrap_vendor_path() -> None:
    vendor_path = vendor_root()
    vendor = str(vendor_path)
    if vendor not in sys.path:
        sys.path.insert(0, vendor)

    os.environ["WT_MODEL_VIEWER_VENDOR_ROOT"] = vendor

    lib_path = vendor_path / "lib"
    if lib_path.exists():
        lib_str = str(lib_path)
        path_entries = os.environ.get("PATH", "").split(os.pathsep)
        if lib_str not in path_entries:
            os.environ["PATH"] = lib_str + os.pathsep + os.environ.get("PATH", "")

        if hasattr(os, "add_dll_directory"):
            handle = os.add_dll_directory(lib_str)
            _DLL_DIRECTORY_HANDLES.append(handle)
