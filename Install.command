#!/bin/bash

# Get the directory where this script lives (LLM-wiki-system-install/)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Run the setup wizard from within this folder
cd "$SCRIPT_DIR" || exit 1

echo "=== LLM Wiki Installer ==="
echo ""
bash "$SCRIPT_DIR/scripts/setup-wizard.sh"

# Keep terminal open after completion
echo ""
read -p "Press Enter to close..." 2>/dev/null
