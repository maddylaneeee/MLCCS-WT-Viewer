from pathlib import Path


project_root = Path.cwd()
src_root = project_root / "src"
script_path = project_root / "luncher.py"
icon_path = src_root / "wt_model_viewer" / "assets" / "MLCCS.ico"
release_package_path = project_root / "dist" / "MLCCS-wt-viewer-win64.zip"
release_checksum_path = project_root / "dist" / "MLCCS-wt-viewer-win64.zip.sha256"


a = Analysis(
    [str(script_path)],
    pathex=[str(project_root), str(src_root)],
    binaries=[],
    datas=[
        (str(icon_path), "wt_model_viewer/assets"),
        (str(release_package_path), "."),
        (str(release_checksum_path), "."),
    ],
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
