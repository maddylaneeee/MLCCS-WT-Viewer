$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$pyinstaller = Join-Path $root ".venv\Scripts\pyinstaller.exe"

if (-not (Test-Path $venvPython)) {
    throw "Missing virtual environment at $venvPython"
}

$env:PIP_USE_PEP517 = "0"

Push-Location $root
try {
    & $venvPython -m pip install setuptools==65.5.0 wheel
    if ($LASTEXITCODE -ne 0) {
        throw "Bootstrap build dependencies failed"
    }

    & $venvPython -m pip install -r (Join-Path $root "requirements.txt")
    if ($LASTEXITCODE -ne 0) {
        throw "Dependency install failed"
    }

    & $pyinstaller --noconfirm --clean (Join-Path $root "WTModelViewer.spec")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed"
    }
}
finally {
    Pop-Location
}
