[CmdletBinding()]
param(
    [string]$Workspace = (Get-Location).Path,
    [string[]]$Agent,
    [switch]$All,
    [string]$Python = '3.12',
    [string]$IndexUrl,
    [string]$Wheelhouse,
    [switch]$Offline
)

$ErrorActionPreference = 'Stop'
$packageRoot = Split-Path -Parent $PSScriptRoot

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "uv was not found; installing it from https://astral.sh/uv ..."
    Invoke-RestMethod https://astral.sh/uv/install.ps1 | Invoke-Expression
    $env:PATH = "$HOME\.local\bin;$HOME\.cargo\bin;$env:PATH"
}
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    throw "uv installation completed but its executable was not found on PATH."
}

$installArguments = @('--system-certs', 'tool', 'install', '--force',
    '--python', $Python)
if ($IndexUrl) {
    $installArguments += @('--default-index', $IndexUrl)
}
if ($Wheelhouse) {
    $installArguments += @('--find-links', (Resolve-Path $Wheelhouse).Path)
}
if ($Offline) {
    $installArguments += '--offline'
}
$installArguments += $packageRoot
& uv @installArguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$toolBin = (& uv tool dir --bin).Trim()
if ($toolBin) { $env:PATH = "$toolBin;$env:PATH" }

$arguments = @('integrate', '--workspace', $Workspace)
foreach ($name in $Agent) {
    $arguments += @('--agent', $name)
}
if ($All) {
    $arguments += '--all'
}

& skillc @arguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$doctorArguments = @('doctor', '--workspace', $Workspace, '--configured')
& skillc @doctorArguments
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "skillc and z3-solver are installed; selected agents now run preflight at SessionStart."