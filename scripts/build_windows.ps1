$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Spec = Join-Path $ProjectRoot 'packaging\windows\privacy_gate.spec'

if (-not (Test-Path $Python)) {
    throw 'Project virtual environment not found. Create .venv and install the project dependencies first.'
}

Push-Location $ProjectRoot
try {
    & $Python -m pytest
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
    & $Python -m PyInstaller --noconfirm --clean $Spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
}
finally {
    Pop-Location
}

