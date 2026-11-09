# PowerShell one-click virtual environment activator for Nemawashi
$venvScript = Join-Path $PSScriptRoot ".venv\Scripts\Activate.ps1"
if (Test-Path $venvScript) {
    & $venvScript
    Write-Host "Nemawashi Python 3.12 Virtual Environment Activated." -ForegroundColor Green
    $env:PYTHONPATH = (Join-Path $PSScriptRoot "src")
    Write-Host "PYTHONPATH set to: $env:PYTHONPATH" -ForegroundColor Cyan
} else {
    Write-Host "Virtual environment not found at $venvScript. Run 'uv venv --python 3.12 .venv' first." -ForegroundColor Red
}
