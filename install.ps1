# Installs the Clawd mascot for Claude Code on Windows.
# Usage (PowerShell):  powershell -ExecutionPolicy Bypass -File .\install.ps1 [-NoOverlay]
param([switch]$NoOverlay)

$ErrorActionPreference = 'Stop'

# Find a real Python 3. Skip the Microsoft Store "python3" stub in WindowsApps,
# which opens the Store instead of running anything.
$python = $null
foreach ($name in 'python', 'python3') {
    $cmd = Get-Command $name -ErrorAction SilentlyContinue |
        Where-Object { $_.Source -notmatch '\\WindowsApps\\' } | Select-Object -First 1
    if ($cmd) { $python = $cmd.Source; break }
}
if (-not $python -and (Get-Command py -ErrorAction SilentlyContinue)) {
    $python = (& py -3 -c 'import sys; print(sys.executable)').Trim()
}
if (-not $python) {
    Write-Error 'Python 3 not found. Install it from https://www.python.org/downloads/ (tick "Add python.exe to PATH") and re-run.'
}

$installArgs = @("$PSScriptRoot\install_windows.py")
if ($NoOverlay) { $installArgs += '--no-overlay' }
& $python @installArgs
exit $LASTEXITCODE
