# Bootstrap script for open-data-jalisco on Windows.
#
# Provisions Python 3.12 via uv, creates the venv, installs deps (incl. dev),
# and copies `.env.example` to `.env` if missing.
#
# Run from the project root:
#   .\scripts\bootstrap.ps1
#
# Requires `uv` on PATH. Install once with:
#   irm https://astral.sh/uv/install.ps1 | iex

$ErrorActionPreference = "Stop"

Write-Host "[1/4] Ensuring Python 3.12 is available via uv..."
uv python install 3.12

Write-Host "[2/4] Creating .venv (Python 3.12)..."
uv venv --python 3.12

Write-Host "[3/4] Installing dependencies (incl. dev extras)..."
uv sync --extra dev

if (-not (Test-Path ".env")) {
    Write-Host "[4/4] Copying .env.example -> .env"
    Copy-Item .env.example .env
} else {
    Write-Host "[4/4] .env already exists — not overwriting."
}

Write-Host ""
Write-Host "Done. Quick checks:"
Write-Host "  uv run pytest tests/unit -v"
Write-Host "  uv run open-data-jalisco --help"
Write-Host "  uv run uvicorn apps.api.main:app --reload --app-dir ."
