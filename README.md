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
- Python 3.10 or newer when running from source
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
- Launcher: `dist\luncher.exe`

## Launcher

`luncher.exe` is a simple installer bootstrap for this project. It downloads the published project zip, extracts it, runs `build.ps1`, then offers to create a desktop shortcut and launch the built application.

Current launcher behavior:

- Downloads `https://lixinchen.ca/docs/MLCCS-wt-viewer.zip`
- Extracts into a local install workspace
- Creates a `.venv` if needed
- Runs the bundled `build.ps1`
- Starts `MLCCS-wt-viewer.exe` after installation if the user chooses to do so

Because the launcher builds from source, the target machine still needs a usable Python 3.10+ environment.

## Repository Layout

- `src/wt_model_viewer/`: desktop application code
- `tests/`: automated tests
- `vendor/dae_runtime/`: bundled parser and native runtime dependencies
- `luncher.py`: launcher source
- `WTModelViewer.spec`: PyInstaller spec for the main application
- `luncher.spec`: PyInstaller spec for the launcher
- `.github/workflows/windows-ci.yml`: Windows CI build and verification workflow

## Scope

This project is a practical local viewer. It does not attempt to fully reproduce Dagor rendering, animations, effects, or LOD switching.

## License

Released under the [MIT License](LICENSE).
