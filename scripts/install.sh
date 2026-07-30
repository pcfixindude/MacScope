#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON=""
for candidate in python3.13 python3.12 /opt/homebrew/bin/python3.13 /opt/homebrew/Caskroom/miniconda/base/bin/python3.12 /usr/bin/python3; do
  if command -v "$candidate" >/dev/null 2>&1; then
    PYTHON="$(command -v "$candidate" 2>/dev/null || true)"
    [[ -x "$candidate" ]] && PYTHON="$candidate"
    break
  fi
  if [[ -x "$candidate" ]]; then
    PYTHON="$candidate"
    break
  fi
done
if [[ -z "$PYTHON" ]]; then
  echo "Python 3.12+ not found." >&2
  exit 1
fi

if [[ ! -d .venv ]]; then
  "$PYTHON" -m venv .venv
fi
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
echo "MacScope dependencies installed into $ROOT/.venv"
