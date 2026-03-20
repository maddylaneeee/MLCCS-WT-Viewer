$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$appName = "MLCCS-wt-viewer"
$releasePackageName = "MLCCS-wt-viewer-win64.zip"
$venvPython = Join-Path $root ".venv\Scripts\python.exe"
$pyinstaller = Join-Path $root ".venv\Scripts\pyinstaller.exe"
$distRoot = Join-Path $root "dist"
$appDistDir = Join-Path $distRoot $appName
$releasePackagePath = Join-Path $distRoot $releasePackageName
$releaseChecksumPath = "$releasePackagePath.sha256"
$launcherPath = Join-Path $distRoot "luncher.exe"

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

function New-ReleasePackage {
    param(
        [Parameter(Mandatory = $true)]
        [string]$SourceDir,
        [Parameter(Mandatory = $true)]
        [string]$ZipPath
    )

    if (-not (Test-Path $SourceDir)) {
        throw "Release source directory not found: $SourceDir"
    }

    Add-Type -AssemblyName System.IO.Compression.FileSystem

    if (Test-Path $ZipPath) {
        Remove-Item $ZipPath -Force
    }

    [System.IO.Compression.ZipFile]::CreateFromDirectory(
        $SourceDir,
        $ZipPath,
        [System.IO.Compression.CompressionLevel]::Optimal,
        $true
    )

    $hash = (Get-FileHash -Path $ZipPath -Algorithm SHA256).Hash.ToLowerInvariant()
    Set-Content -Path "$ZipPath.sha256" -Value "$hash  $(Split-Path -Leaf $ZipPath)" -Encoding ascii
}

function Test-LauncherBundle {
    param(
        [Parameter(Mandatory = $true)]
        [string]$LauncherPath
    )

    if (-not (Test-Path $LauncherPath)) {
        throw "Launcher executable not found: $LauncherPath"
    }

    $validationScript = @"
from pathlib import Path
from PyInstaller.archive.readers import CArchiveReader

launcher = Path(r"$LauncherPath")
archive = CArchiveReader(str(launcher))
required = {"MLCCS-wt-viewer-win64.zip", "MLCCS-wt-viewer-win64.zip.sha256"}
missing = sorted(required - set(archive.toc.keys()))
if missing:
    raise SystemExit(f"Launcher bundle is missing embedded payload: {', '.join(missing)}")
print(f"Validated launcher payload: {launcher}")
"@

    $validationScript | & $venvPython -
    if ($LASTEXITCODE -ne 0) {
        throw "Launcher payload validation failed"
    }
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

    & $pyinstaller --noconfirm --clean (Join-Path $root "WTModelViewer.spec")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed for WTModelViewer.spec"
    }

    New-ReleasePackage -SourceDir $appDistDir -ZipPath $releasePackagePath
    Write-Host "Release package created: $releasePackagePath"
    Write-Host "Release checksum created: $releaseChecksumPath"

    & $pyinstaller --noconfirm --clean (Join-Path $root "luncher.spec")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed for luncher.spec"
    }

    Test-LauncherBundle -LauncherPath $launcherPath
}
finally {
    Pop-Location
}
