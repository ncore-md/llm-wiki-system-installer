#!/bin/bash
# Convenience wrapper for the setup wizard.
# Usage:
#   Interactive:  bash llm-wiki-system-installer/run.sh
#   Agent (non-interactive):
#     export SETUP_MODE=1 SETUP_VAULT_NAME="MyWiki"
#     bash llm-wiki-system-installer/run.sh
#   Or with args:  SETUP_MODE=1 SETUP_VAULT_NAME="MyWiki" bash llm-wiki-system-installer/run.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$SCRIPT_DIR/scripts/setup-wizard.sh"
