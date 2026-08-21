param(
    [Parameter(Mandatory = $true)] [string]$PackageIdentityName,
    [Parameter(Mandatory = $true)] [string]$Publisher,
    [Parameter(Mandatory = $true)] [string]$PublisherDisplayName,
    [string]$Version = '0.4.2.0',
    [string]$MakeAppx = ''
)

$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$DistDir = Join-Path $ProjectRoot 'dist\AI PM LAB Privacy Gate'
$Template = Join-Path $ProjectRoot 'packaging\windows\msix\AppxManifest.template.xml'
$Staging = Join-Path $ProjectRoot 'build\msix\layout'
$Assets = Join-Path $Staging 'Assets'
$ReleaseDir = Join-Path $ProjectRoot 'release'
$Output = Join-Path $ReleaseDir "AI_PM_LAB_Privacy_Gate_${Version}_x64.msix"

if ($Version -notmatch '^\d+\.\d+\.\d+\.\d+$') {
    throw 'MSIX Version must contain four numeric components, for example 0.4.2.0.'
}
if (-not (Test-Path -LiteralPath $Python)) { throw 'Project virtual environment not found.' }
if (-not (Test-Path -LiteralPath (Join-Path $DistDir 'AI PM LAB Privacy Gate.exe'))) {
    throw 'Windows distribution not found. Run scripts\build_windows.ps1 first.'
}

if (-not $MakeAppx) {
    $sdkRoot = Join-Path ${env:ProgramFiles(x86)} 'Windows Kits\10\bin'
    $MakeAppx = Get-ChildItem -LiteralPath $sdkRoot -Recurse -Filter 'MakeAppx.exe' `
        -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -match '\\x64\\MakeAppx\.exe$' } |
        Sort-Object FullName -Descending |
        Select-Object -First 1 -ExpandProperty FullName
}
if (-not $MakeAppx -or -not (Test-Path -LiteralPath $MakeAppx)) {
    throw 'MakeAppx.exe was not found. Install the Windows SDK or MSIX Packaging Tool.'
}

if (Test-Path -LiteralPath $Staging) {
    Remove-Item -LiteralPath $Staging -Recurse -Force
}
New-Item -ItemType Directory -Force $Staging, $Assets, $ReleaseDir | Out-Null
Copy-Item -Path (Join-Path $DistDir '*') -Destination $Staging -Recurse -Force

# python-docx ships both the runtime default.docx file and an expanded copy of
# that same OPC package for its own source distribution. MSIX reserves `_rels`
# directories for its package metadata and therefore cannot contain the expanded
# copy. The application uses templates\default.docx at runtime, so omit only the
# redundant source tree from the Store package.
$ExpandedDocxTemplate = Join-Path $Staging '_internal\docx\templates\default-docx-template'
if (Test-Path -LiteralPath $ExpandedDocxTemplate) {
    Remove-Item -LiteralPath $ExpandedDocxTemplate -Recurse -Force
}
& $Python (Join-Path $ProjectRoot 'scripts\create_msix_assets.py') $Assets
if ($LASTEXITCODE -ne 0) { throw 'MSIX asset generation failed.' }

function Escape-Xml([string]$Value) {
    return [System.Security.SecurityElement]::Escape($Value)
}

$manifest = Get-Content -LiteralPath $Template -Raw
$manifest = $manifest.Replace('__PACKAGE_IDENTITY_NAME__', (Escape-Xml $PackageIdentityName))
$manifest = $manifest.Replace('__PUBLISHER__', (Escape-Xml $Publisher))
$manifest = $manifest.Replace('__PUBLISHER_DISPLAY_NAME__', (Escape-Xml $PublisherDisplayName))
$manifest = $manifest.Replace('__VERSION__', $Version)
Set-Content -LiteralPath (Join-Path $Staging 'AppxManifest.xml') `
    -Value $manifest -Encoding utf8

& $MakeAppx pack /o /d $Staging /p $Output
if ($LASTEXITCODE -ne 0) { throw 'MakeAppx failed to build the MSIX package.' }
Get-Item -LiteralPath $Output | Select-Object FullName, Length, LastWriteTime
