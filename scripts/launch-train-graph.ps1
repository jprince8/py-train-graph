# scripts\launch-train-graph.ps1

Param(
    [Parameter(ValueFromRemainingArguments=$true)]
    [String[]] $Args
)

# Ensure we run from the repo root
$scriptDir = Split-Path $MyInvocation.MyCommand.Path -Parent
$repoRoot = Join-Path $scriptDir ".." | Resolve-Path
Push-Location $repoRoot

$venv = ".\.venv"

if (-Not (Test-Path "$venv\Scripts\Activate.ps1")) {
    Write-Host "Creating virtual environment..."
    python -m venv $venv
    & "$venv\Scripts\Activate.ps1"
    pip install -e .
} else {
    & "$venv\Scripts\Activate.ps1"
}

# Forward all args to the CLI
py-train-graph @Args

Pop-Location
