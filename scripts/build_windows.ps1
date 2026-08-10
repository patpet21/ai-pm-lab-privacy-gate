$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot '.venv\Scripts\python.exe'
$Spec = Join-Path $ProjectRoot 'packaging\windows\privacy_gate.spec'
$McpScript = Join-Path $ProjectRoot 'run_mcp.py'
$McpDist = Join-Path $ProjectRoot 'dist\AI PM LAB Privacy Gate'
$McpWork = Join-Path $ProjectRoot 'build\privacy-gate-mcp'

if (-not (Test-Path $Python)) {
    throw 'Project virtual environment not found. Create .venv and install the project dependencies first.'
}

Push-Location $ProjectRoot
try {
    & $Python -m pytest
    if ($LASTEXITCODE -ne 0) { throw 'Tests failed; build stopped.' }
    & $Python -m PyInstaller --noconfirm --clean $Spec
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    & $Python -m PyInstaller --noconfirm --clean --onedir --console `
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
}
finally {
    Pop-Location
}
