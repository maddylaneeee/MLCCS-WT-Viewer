# MLCCS-wt-viewer

Windows desktop viewer for local War Thunder `RendInst` and `DynModel` assets.

## Highlights

- Scans local `.grp` packs under the War Thunder game directory.
- Resolves textures from `content/base/res/**/*.dxp.bin` and available `content.hq/**/res/**/*.dxp.bin` packs.
- Restores common `DynModel` transforms and sibling resources to avoid folded geometry.
- Handles practical texture and material recovery for local viewing, including `diffuse`, `normal`, `AO`, `mask`, `detail`, and `detail normal` paths.
- Preserves runtime UV orientation and applies common Dagor shader-family tuning for opaque, cutout, glass, and masked materials.
- Supports model variants such as base, damage, and x-ray forms.
- Keeps the GUI responsive with background scanning, vectorized scene extraction, indexed drawing, and staged GPU uploads.
- Provides bilingual UI support with automatic detection plus manual `English`, `中文`, and `日本語` selection.
- Includes viewport light presets with remembered user settings.

## Requirements

- Windows 10 or newer
- Python 3.10 when running from source
- A local War Thunder installation or extracted asset directory

## Running From Source

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m wt_model_viewer.main
```

## Testing

```powershell
.\.venv\Scripts\python -m unittest discover -s tests
.\.venv\Scripts\python -m compileall src
```

## Build

```powershell
.\build.ps1
```

The packaged application is written to `dist\MLCCS-wt-viewer\`.

## Repository Layout

- `src/wt_model_viewer/`: application code
- `tests/`: automated tests
- `vendor/dae_runtime/`: bundled runtime parser and native dependencies
- `.github/workflows/windows-ci.yml`: Windows CI build and verification workflow

## Scope Notes

This project is intended as a practical local viewer. It does not currently attempt to fully reproduce Dagor rendering, animations, effects, or LOD switching.

## License

Released under the [MIT License](LICENSE).
