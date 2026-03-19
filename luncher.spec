from pathlib import Path


project_root = Path.cwd()
src_root = project_root / "src"
script_path = project_root / "luncher.py"
icon_path = src_root / "wt_model_viewer" / "assets" / "MLCCS.ico"


a = Analysis(
    [str(script_path)],
    pathex=[str(project_root), str(src_root)],
    binaries=[],
    datas=[(str(icon_path), "wt_model_viewer/assets")],
    hiddenimports=[],
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
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="luncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_path),
)
