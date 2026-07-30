#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if [[ -f requirements-dev.txt ]]; then
  python -m pip install -r requirements-dev.txt
fi
echo "Dependencies updated."
