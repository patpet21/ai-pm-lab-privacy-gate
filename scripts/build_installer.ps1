param(
    [string]$InnoCompiler = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$DistDir = Join-Path $ProjectRoot 'dist\AI PM LAB Privacy Gate'
$ReleaseDir = Join-Path $ProjectRoot 'release'
$InstallerScript = Join-Path $ProjectRoot 'packaging\windows\installer.iss'

if (-not (Test-Path -LiteralPath $Python)) {
    throw 'Project virtual environment not found.'
}
if (-not (Test-Path (Join-Path $DistDir 'AI PM LAB Privacy Gate.exe'))) {
    throw 'Windows distribution not found. Run build_windows.ps1 first.'
}

$Version = (& $Python -c "import ai_pm_lab_privacy_gate; print(ai_pm_lab_privacy_gate.__version__)").Trim()
if ($LASTEXITCODE -ne 0 -or $Version -notmatch '^\d+\.\d+\.\d+$') {
    throw "Unable to resolve a valid PrivacyGate release version. Received '$Version'."
}
$VersionInfo = "$Version.0"

if (-not $InnoCompiler) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 7\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 7\ISCC.exe"
    )
    $InnoCompiler = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

if (-not $InnoCompiler -or -not (Test-Path $InnoCompiler)) {
    throw 'ISCC.exe not found. Install Inno Setup and rerun this script.'
}

New-Item -ItemType Directory -Force $ReleaseDir | Out-Null
& $InnoCompiler `
    "/DDistDir=$DistDir" `
    "/DReleaseDir=$ReleaseDir" `
    "/DMyAppVersion=$Version" `
    "/DMyAppVersionInfo=$VersionInfo" `
    $InstallerScript
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }

$ExpectedName = "AI_PM_LAB_Privacy_Gate_Setup_$Version.exe"
$Installer = Join-Path $ReleaseDir $ExpectedName
if (-not (Test-Path -LiteralPath $Installer)) {
    throw "Expected installer was not generated: $ExpectedName"
}
Get-Item -LiteralPath $Installer | Select-Object FullName, Length, LastWriteTime
