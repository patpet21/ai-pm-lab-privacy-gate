param(
    [string]$InnoCompiler = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$DistDir = Join-Path $ProjectRoot 'dist\AI PM LAB Privacy Gate'
$ReleaseDir = Join-Path $ProjectRoot 'release'
$InstallerScript = Join-Path $ProjectRoot 'packaging\windows\installer.iss'

if (-not (Test-Path (Join-Path $DistDir 'AI PM LAB Privacy Gate.exe'))) {
    throw 'Windows distribution not found. Run build_windows.ps1 first.'
}

if (-not $InnoCompiler) {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 7\ISCC.exe",
        "$env:ProgramFiles(x86)\Inno Setup 7\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 7\ISCC.exe"
    )
    $InnoCompiler = $candidates | Where-Object { $_ -and (Test-Path $_) } | Select-Object -First 1
}

if (-not $InnoCompiler -or -not (Test-Path $InnoCompiler)) {
    throw 'ISCC.exe not found. Install Inno Setup and rerun this script.'
}

New-Item -ItemType Directory -Force $ReleaseDir | Out-Null
& $InnoCompiler "/DDistDir=$DistDir" "/DReleaseDir=$ReleaseDir" $InstallerScript
if ($LASTEXITCODE -ne 0) { throw 'Inno Setup compilation failed.' }

Get-ChildItem $ReleaseDir -Filter 'AI_PM_LAB_Privacy_Gate_Setup_*.exe' |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1 FullName, Length, LastWriteTime

