$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Spec = Join-Path $ProjectRoot 'packaging\windows\privacy_gate.spec'
$McpScript = Join-Path $ProjectRoot 'run_mcp.py'
$McpDist = Join-Path $ProjectRoot 'dist\AI PM LAB Privacy Gate'
$McpWork = Join-Path $ProjectRoot 'build\privacy-gate-mcp'
$CloudflaredVersion = '2026.7.3'
$CloudflaredSha256 = '8635DA433B6DF8194746E88ED9D2589566C20E38BFC2A80E431A348B7C765841'

if (-not (Test-Path $Python)) {
    throw 'Project virtual environment not found. Create .venv and install the project dependencies first.'
}

Push-Location $ProjectRoot
try {
    & $Python -m pytest
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
    & $Python -m PyInstaller --noconfirm --clean $Spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    & $Python -m PyInstaller --noconfirm --clean --onedir --windowed `
        --name 'AI PM LAB Privacy Gate MCP' `
        --distpath $McpDist `
        --workpath $McpWork `
        --specpath $McpWork `
        --paths (Join-Path $ProjectRoot 'src') `
        --collect-all mcp `
        --copy-metadata mcp `
        --copy-metadata mcp-types `
        $McpScript
    if ($LASTEXITCODE -ne 0) { throw 'MCP server build failed.' }

    # Bundle the outbound-only secure-link component beside the application.
    # Customer installs never depend on a developer path or system install.
    $CloudflaredDestination = Join-Path $McpDist 'cloudflared.exe'
    $CloudflaredCandidates = @(
        $env:PRIVACY_GATE_CLOUDFLARED,
        (Join-Path ${env:ProgramFiles(x86)} 'cloudflared\cloudflared.exe'),
        (Join-Path $env:ProgramFiles 'cloudflared\cloudflared.exe')
    ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    $CloudflaredSource = $CloudflaredCandidates | Select-Object -First 1
    if ($CloudflaredSource) {
        Copy-Item -LiteralPath $CloudflaredSource -Destination $CloudflaredDestination -Force
    }
    else {
        $DownloadUrl = "https://github.com/cloudflare/cloudflared/releases/download/$CloudflaredVersion/cloudflared-windows-amd64.exe"
        Invoke-WebRequest -Uri $DownloadUrl -OutFile $CloudflaredDestination
    }
    $ActualHash = (Get-FileHash -LiteralPath $CloudflaredDestination -Algorithm SHA256).Hash
    if ($ActualHash -ne $CloudflaredSha256) {
        throw "cloudflared checksum mismatch. Expected $CloudflaredSha256 but received $ActualHash."
    }
}
finally {
    Pop-Location
}
