# MLCCS-wt-viewer

Windows desktop viewer for local War Thunder `RendInst` and `DynModel` assets.

## Features

- Scans local `.grp` packs under the War Thunder game directory.
- Resolves textures from `content/base/res/**/*.dxp.bin` and available `content.hq/**/res/**/*.dxp.bin` packs.
- Restores common `DynModel` transforms and sibling resources to avoid folded geometry.
- Recovers practical Dagor material inputs for local viewing, including `diffuse`, `normal`, `AO`, `mask`, `detail`, and `detail normal` paths.
- Preserves runtime UV orientation and applies shader-family tuning for opaque, cutout, glass, and masked materials.
- Supports common model variants such as base, damage, and x-ray forms.
- Keeps the GUI responsive with background scanning, vectorized scene extraction, indexed drawing, and staged GPU uploads.
- Provides bilingual UI support with automatic detection plus manual `English`, `中文`, and `日本語` selection.
- Includes viewport light presets with persisted user settings.

## Requirements

- Windows 10 or newer
- Python 3.10 or newer when running from source or building release artifacts
- PowerShell 5.1 or newer for `build.ps1`
- A local War Thunder installation or extracted asset directory

## Run From Source

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m wt_model_viewer.main
```

## Test

```powershell
.\.venv\Scripts\python -m unittest discover -s tests
.\.venv\Scripts\python -m compileall src luncher.py
```

## Build

```powershell
.\build.ps1
```

Build outputs:

- Main application: `dist\MLCCS-wt-viewer\MLCCS-wt-viewer.exe`
- Release package for launcher deployment: `dist\MLCCS-wt-viewer-win64.zip`
- Release package checksum: `dist\MLCCS-wt-viewer-win64.zip.sha256`
- Launcher: `dist\luncher.exe`

## Launcher

`luncher.exe` is a Windows bootstrap installer for this project. The packaged onefile launcher embeds the prebuilt application package and can install on a clean client machine without Python, pip, a virtual environment, or PyInstaller. If no embedded package is available, the source form can still fall back to the published download URL.

Current launcher behavior:

- Uses the embedded `MLCCS-wt-viewer-win64.zip` package when running the packaged launcher
- Optionally verifies the embedded or remote SHA256 checksum when available
- Falls back to `https://lixinchen.ca/docs/MLCCS-wt-viewer-win64.zip` only when no embedded package is present
- Extracts into a local install workspace
- Replaces the previous installed app directory in one step
- Starts `MLCCS-wt-viewer.exe` after installation if the user chooses to do so

The target machine does not need Python, pip, a virtual environment, or PyInstaller. The packaged launcher already carries the release payload it needs.

## Repository Layout

- `src/wt_model_viewer/`: desktop application code
- `tests/`: automated tests
- `vendor/dae_runtime/`: bundled parser and native runtime dependencies
- `luncher.py`: launcher source
- `dist\MLCCS-wt-viewer-win64.zip`: release package consumed by the launcher
- `WTModelViewer.spec`: PyInstaller spec for the main application
- `luncher.spec`: PyInstaller spec for the launcher
- `.github/workflows/windows-ci.yml`: Windows CI build and verification workflow

## Scope

This project is a practical local viewer. It does not attempt to fully reproduce Dagor rendering, animations, effects, or LOD switching.

## License

Released under the [MIT License](LICENSE).
