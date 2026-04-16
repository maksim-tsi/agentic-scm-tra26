#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

if ! command -v uv >/dev/null 2>&1; then
  echo "Missing dependency: uv" >&2
  echo "Install uv: https://docs.astral.sh/uv/" >&2
  exit 1
fi

export PYTHONPATH="src:."

UV_CACHE_DIR="${UV_CACHE_DIR:-.uv-cache}"
uv --cache-dir "$UV_CACHE_DIR" sync --dev --frozen

echo "Environment ready."
echo "Tip: cp .env.example .env"
