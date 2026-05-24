#!/bin/bash
# Convenience wrapper for the setup wizard.
# Usage:
#   Interactive:  bash LLM-wiki-system-install/run.sh
#   Agent (non-interactive):
#     export SETUP_MODE=1 SETUP_VAULT_NAME="MyWiki"
#     bash LLM-wiki-system-install/run.sh
#   Or with args:  SETUP_MODE=1 SETUP_VAULT_NAME="MyWiki" bash LLM-wiki-system-install/run.sh

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec bash "$SCRIPT_DIR/scripts/setup-wizard.sh"
