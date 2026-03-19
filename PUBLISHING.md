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

Attach the generated `dist\MLCCS-wt-viewer` folder or a zip exported from it to a GitHub Release.

## Repository Notes

- Generated outputs and local virtual environments are ignored by Git.
- A Windows GitHub Actions workflow is included to run tests, `compileall`, and the PyInstaller build on pushes and pull requests.
- The repository is released under the MIT License.
