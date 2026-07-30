#!/bin/zsh
set -euo pipefail
DATA="$HOME/Library/Application Support/MacScope"
echo "This will remove MacScope local data under:"
echo "  $DATA"
read -r "REPLY?Type RESET to continue: "
if [[ "$REPLY" != "RESET" ]]; then
  echo "Cancelled."
  exit 1
fi
rm -rf "$DATA"
echo "Local MacScope data removed."
