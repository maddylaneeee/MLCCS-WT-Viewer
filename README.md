# MLCCS-wt-viewer

Minimal Windows GUI viewer for local War Thunder `RendInst` / `DynModel` assets.

## Status

- Windows-only project.
- Source tree is prepared for GitHub publishing.
- Generated outputs such as `.venv`, `build`, and `dist` are intentionally not part of the repository copy.

## Scope

- User manually selects a War Thunder root folder.
- The app scans `content/base/res/**/*.grp`.
- Texture discovery covers `content/base/res/**/*.dxp.bin` plus available `content.hq/**/res/**/*.dxp.bin` packs, and the index is prepared during scan so first model load does not have to rebuild it.
- Indexed resources include `RendInst` and `DynModel` entries exposed through the `.grp` packs.
- Models with `*_dmg` / `*_xray` suffixes are grouped under the base name and exposed through a variant selector.
- Selected models render in an interactive 3D viewport with rotate / pan / zoom.
- Material approximation includes `diffuse`, `normal`, `AO`, `mask`, `detail`, and `detail normal` when those textures can be resolved from `.dxp.bin` packs, with the runtime UV orientation preserved, Dagor-style normal texture conversion, shader-class-based alpha handling for opaque, cutout, and blended materials, and extra AO/spec/glass tuning for common War Thunder shader families.
- `DynModel` objects cache sibling resources from the same `.grp` pack so default node transforms and merged skinned mesh geometry can restore the intended pose instead of folded geometry.
- The viewport exposes light presets plus manual azimuth, elevation, and brightness controls, and the last-used light setup is restored on the next launch.
- Application branding is renamed to `MLCCS-wt-viewer`, and the `MLCCS.ico` logo is bundled for the packaged app while runtime icon caching still prefers the local cache and refreshes from the configured URL when needed.
- UI language supports automatic detection from `config.blk` plus manual `English` / `中文` / `日本語` selection.
- Scanning and CPU scene building run on a background worker, scene extraction is vectorized with NumPy for heavy models, batches are uploaded with indexed drawing (`VBO + EBO`, with `uint16` indices when possible), repeated GPU texture uploads are deduplicated within the current scene, and GPU uploads are batched across frames so the GUI remains responsive during heavy loads.
- No full Dagor material recreation, no animation playback, no effects, no LOD switching.

## Run

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\.venv\Scripts\python -m wt_model_viewer.main
```

## Test

```powershell
.\.venv\Scripts\python -m unittest discover -s tests
.\.venv\Scripts\python -m compileall src
```

## Build

```powershell
.\build.ps1
```

The packaged executable is written under `dist\MLCCS-wt-viewer\`.

## GitHub Publishing

- `.gitignore` and `.gitattributes` are included for a clean repository import.
- A GitHub Actions workflow is included at `.github/workflows/windows-ci.yml`.
- Publish steps are documented in `PUBLISHING.md`.
- A `LICENSE` file is still intentionally absent until you choose the release terms.
