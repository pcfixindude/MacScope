#!/bin/zsh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VERSION="$(tr -d '[:space:]' < VERSION)"
OUT="$ROOT/dist"
mkdir -p "$OUT"
STAGE="$OUT/MacScope-$VERSION"
rm -rf "$STAGE"
mkdir -p "$STAGE"

rsync -a \
  --exclude '.venv' \
  --exclude '.venv312' \
  --exclude '__pycache__' \
  --exclude '.pytest_cache' \
  --exclude '.git' \
  --exclude 'macscope.db' \
  --exclude 'macscope.log' \
  --exclude 'dist' \
  --exclude '*.pyc' \
  --exclude '.DS_Store' \
  "$ROOT/" "$STAGE/"

(
  cd "$OUT"
  rm -f "MacScope-$VERSION.zip"
  zip -rq "MacScope-$VERSION.zip" "MacScope-$VERSION"
)
echo "Release ZIP: $OUT/MacScope-$VERSION.zip"
