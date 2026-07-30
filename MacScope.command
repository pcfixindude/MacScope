#!/bin/zsh
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"
DATA="$HOME/Library/Application Support/MacScope"
LOG_DIR="$DATA/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/launcher.log"

exec >>"$LOG_FILE" 2>&1
echo "---- $(date) starting MacScope ----"

pick_python() {
  for candidate in \
    "$ROOT/.venv/bin/python" \
    python3.13 \
    python3.12 \
    /opt/homebrew/bin/python3.13 \
    /opt/homebrew/Caskroom/miniconda/base/bin/python3.12 \
    /usr/bin/python3
  do
    if [[ -x "$candidate" ]]; then
      echo "$candidate"
      return 0
    fi
    if command -v "$candidate" >/dev/null 2>&1; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

PYTHON="$(pick_python)" || {
  osascript -e 'display alert "MacScope" message "Python 3.12+ is required." as critical'
  exit 1
}

if [[ ! -d "$ROOT/.venv" ]]; then
  "$PYTHON" -m venv "$ROOT/.venv"
fi
source "$ROOT/.venv/bin/activate"

MARKER="$ROOT/.venv/.deps-installed"
REQ_HASH="$(cksum requirements.txt | awk '{print $1}')"
if [[ ! -f "$MARKER" ]] || [[ "$(cat "$MARKER" 2>/dev/null)" != "$REQ_HASH" ]]; then
  python -m pip install --upgrade pip
  python -m pip install -r requirements.txt
  echo "$REQ_HASH" >"$MARKER"
fi

# Detect already-running instance
if curl -fsS http://127.0.0.1:8501 >/dev/null 2>&1; then
  open "http://127.0.0.1:8501"
  exit 0
fi

exec python -m streamlit run app.py --server.headless false
