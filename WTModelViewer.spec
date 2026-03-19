import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


project_root = Path.cwd()
vendor_root = project_root / "vendor" / "dae_runtime"
src_root = project_root / "src"
main_script = src_root / "wt_model_viewer" / "main.py"
icon_path = src_root / "wt_model_viewer" / "assets" / "MLCCS.ico"
app_name = "MLCCS-wt-viewer"

sys.path.insert(0, str(src_root))
sys.path.insert(0, str(vendor_root))

binaries = []
for dll_path in (vendor_root / "lib").glob("*.dll"):
    binaries.append((str(dll_path), "vendor/dae_runtime/lib"))

hiddenimports = collect_submodules("parse") + collect_submodules("util")


a = Analysis(
    [str(main_script)],
    pathex=[str(src_root), str(vendor_root)],
    binaries=binaries,
    datas=[(str(icon_path), "wt_model_viewer/assets")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_path),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name=app_name,
)
