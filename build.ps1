$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$pyinstaller = Join-Path $root ".venv\Scripts\pyinstaller.exe"

function Find-PythonCommand {
    $candidates = @(
        @("py", "-3.10"),
        @("py", "-3"),
        @("py"),
        @("python"),
        @("python3")
    )

    foreach ($candidate in $candidates) {
        $command = $candidate[0]
        $args = @()
        if ($candidate.Count -gt 1) {
            $args = $candidate[1..($candidate.Count - 1)]
        }

        try {
            & $command @args --version | Out-Null
            if ($LASTEXITCODE -eq 0) {
                return @($command) + $args
            }
        }
        catch {
        }
    }

    throw "Python 3.10 or newer is required to bootstrap the build environment."
}

if (-not (Test-Path $venvPython)) {
    $pythonCommand = Find-PythonCommand
    $pythonArgs = @()
    if ($pythonCommand.Length -gt 1) {
        $pythonArgs = $pythonCommand[1..($pythonCommand.Length - 1)]
    }
    & $pythonCommand[0] @pythonArgs -m venv (Join-Path $root ".venv")
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $venvPython)) {
        throw "Failed to create virtual environment at $venvPython"
    }
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

    foreach ($specName in @("WTModelViewer.spec", "luncher.spec")) {
        & $pyinstaller --noconfirm --clean (Join-Path $root $specName)
        if ($LASTEXITCODE -ne 0) {
            throw "PyInstaller build failed for $specName"
        }
    }
}
finally {
    Pop-Location
}
