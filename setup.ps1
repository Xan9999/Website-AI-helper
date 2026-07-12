# One-command setup (Windows / PowerShell): creates a venv and installs the tool.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -e .
Write-Host ""
Write-Host "Installed. Next:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "  website-ai-helper init"
Write-Host "  website-ai-helper ingest https://your-site.com --collection mysite"
Write-Host "  website-ai-helper serve --collection mysite"
