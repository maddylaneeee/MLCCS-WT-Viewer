# Publishing To GitHub

## Before First Push

1. Set your local Git identity.
2. Create an empty GitHub repository.

```powershell
git config --global user.name "Your Name"
git config --global user.email "you@example.com"
```

## Initialize And Push

```powershell
git init -b main
git add .
git commit -m "Initial GitHub import"
git remote add origin https://github.com/<owner>/MLCCS-wt-viewer.git
git push -u origin main
```

## Build A Release Package

```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
.\build.ps1
```

Generated outputs:

- `dist\MLCCS-wt-viewer\` - unpacked packaged app
- `dist\MLCCS-wt-viewer-win64.zip` - prebuilt release package consumed by `luncher.exe`
- `dist\MLCCS-wt-viewer-win64.zip.sha256` - optional checksum file consumed by `luncher.exe`
- `dist\luncher.exe` - bootstrap installer that embeds the release package for clean-machine installation

Publish `MLCCS-wt-viewer-win64.zip` and `MLCCS-wt-viewer-win64.zip.sha256` to `https://lixinchen.ca/docs/`.

## Repository Notes

- Generated outputs and local virtual environments are ignored by Git.
- A Windows GitHub Actions workflow is included to run tests, `compileall`, and the PyInstaller build on pushes and pull requests.
- The repository is released under the MIT License.
