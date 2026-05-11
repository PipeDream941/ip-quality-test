# run.ps1 - Windows launcher for ip-quality-test
# Usage:
#   .\run.ps1                                  # test local egress
#   .\run.ps1 -Label jp-01                     # custom label
#   .\run.ps1 -Proxy 'http://127.0.0.1:6174'   # test through a proxy
#   .\run.ps1 -Ip 1.1.1.1 -Label cf-dns        # test an arbitrary IP

[CmdletBinding()]
param(
    [string]$Label = 'local',
    [string]$Proxy = '',
    [string]$Ip = '',
    [string]$OutDir = '',
    [switch]$NoColor,
    [switch]$JsonOnly
)

$ErrorActionPreference = 'Stop'
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$pyCmd = $null
foreach ($candidate in 'python','py','python3') {
    $found = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($found) { $pyCmd = $found; break }
}
if (-not $pyCmd) {
    Write-Error 'Python 3.7+ is required. Install via `winget install Python.Python.3.12` or from python.org.'
    exit 2
}

$cliArgs = @(
    (Join-Path $scriptDir 'scripts\ip_quality.py'),
    '--label', $Label
)
if ($Proxy)    { $cliArgs += @('--proxy', $Proxy) }
if ($Ip)       { $cliArgs += @('--ip', $Ip) }
if ($OutDir)   { $cliArgs += @('--out-dir', $OutDir) }
if ($NoColor)  { $cliArgs += '--no-color' }
if ($JsonOnly) { $cliArgs += '--json-only' }

& $pyCmd.Source @cliArgs
exit $LASTEXITCODE
