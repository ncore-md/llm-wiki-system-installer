#!/usr/bin/env bash
# LLM Wiki Setup Wizard — Initialize a clean knowledge base in an Obsidian vault.
# Self-contained: copies system files from sibling directories within this llm-wiki-system-installer/ folder.
# Usage (interactive): bash llm-wiki-system-installer/scripts/setup-wizard.sh
# Usage (agent/non-interactive): see environment variables below.
#
# Portable — send the entire llm-wiki-system-installer/ folder to another user. They extract it and run:
#   bash llm-wiki-system-installer/scripts/setup-wizard.sh

set -e
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ─── Self-Contained: Find bundled setup files relative to this script ──
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SETUP_SRC="$SCRIPT_DIR/.."

if [ ! -d "$SETUP_SRC" ]; then
    error "Setup folder not found at $SETUP_SRC"
    info "Extract the llm-wiki-system-installer/ folder and run from there."
    exit 1
fi

# ─── Quick Guide: What is LLM Wiki? ──────────────────────────────────
print_guide() {
    echo ""
    info "═══════════════════════════════════════════════════"
    echo ""
    info "  LLM Wiki — Knowledge Base for Agentic AI"
    echo ""
    cat << 'GUIDE'

  LLM Wiki turns raw source material into organized, queryable
  knowledge that AI agents and humans can use.

  What it does:
    • Ingests articles, notes, transcripts → Raw/Sources/
    • Compiles them into structured Wiki notes (Concepts, Topics, Entities)
    • Maintains a searchable catalog for fast retrieval
    • Validates quality on every commit (lint, build, source checks)

  How to use:
    1. Add raw sources as cleaned Markdown in Raw/Sources/
    2. Run the ingest skill (.agents/skills/llm-wiki-ingest/) or
       follow AGENTS.md for the full workflow
    3. Query the catalog to find existing knowledge before work
       (use .agents/skills/llm-wiki-query/) before creating new notes
    4. Create or update Wiki notes in the correct subfolder:
       Concepts → Wiki/Concepts/, Topics → Wiki/Topics/

  Architecture:
    Raw/       → Source material (never modified)
    Wiki/      → Compiled knowledge (queryable, linked)
                 Concepts/, Topics/, Entities/, Projects/, Logs/
    Schema/    → Rules and validation definitions
    scripts/   → Validation tools (wiki_tool.py)
                 build, lint, search-catalog, source-lint
    .agents/   → Agent skills (ingest, query, lint, maintain)

GUIDE
    echo "  ═══════════════════════════════════════════════════"
    echo ""

    info "  Agent usage (non-interactive):"
    cat << 'AGENTS'

    IMPORTANT: Agents must use environment variables — do NOT interact with prompts.

    Required env vars for new vault:
      SETUP_MODE=1              # 1 = create new, 2 = apply to existing
      SETUP_VAULT_NAME="MyWiki" # name of the new vault (required for mode 1)
      SETUP_CONFIRM=y           # skip confirmation prompt

    Optional env vars:
      SETUP_VAULT_PATH="/path"  # override default vault location
                                # Default: .llm-wiki/ sibling to llm-wiki-system-installer/

    Example — create new vault:
      export SETUP_MODE=1
      export SETUP_VAULT_NAME="MyWiki"
      bash llm-wiki-system-installer/scripts/setup-wizard.sh

    Example — apply to existing vault:
      export SETUP_MODE=2
      bash llm-wiki-system-installer/scripts/setup-wizard.sh   # prompts for vault selection

AGENTS
}

# ─── Prerequisite Checks ──────────────────────────────────────────────
info "Checking prerequisites..."

# 1. Check if Obsidian CLI is available
if command -v obsidian &> /dev/null; then
    success "Obsidian CLI found: $(which obsidian)"
else
    warn "Obsidian CLI not found in PATH."
    info "You can still create a vault structure manually, but features like"
    info "dead link detection and task management will require manual setup."
fi

# 2. Check if Obsidian app is running (for CLI-dependent features)
if command -v obsidian &> /dev/null; then
    if obsidian version &> /dev/null 2>&1; then
        OSSION_VERSION=$(obsidian version 2>/dev/null | head -1)
        success "Obsidian is running: $OSSION_VERSION"
    else
        warn "Obsidian CLI found but app is not running."
        info "Features like dead link detection and task management are unavailable"
        info "until Obsidian is launched. Vault creation will still work."
    fi
fi

# 3. Check if Python is available (for wiki_tool validation)
if command -v python3 &> /dev/null; then
    PYTHON_VER=$(python3 --version 2>&1 | sed -n 's/Python \([0-9]*\.[0-9]*\).*/1/p')
    success "Python $PYTHON_VER found"
else
    warn "python3 not found. Validation commands won't be available."
fi

# ─── Obsidian Vault Registration ──────────────────────────────────────
_register_obsidian_vault() {
  local vault_path="$1"
  local obssi_config="$HOME/Library/Application Support/Obsidian/obsidian.json"

  # Create .obsidian/app.json in the vault (Obsidian needs this to recognize the folder)
  local obsidian_dir="${vault_path}/.obsidian"
  mkdir -p "$obsidian_dir"
  if [[ ! -f "$obsidian_dir/app.json" ]]; then
    printf '{\n  "alwaysUpdateLinks": true,\n  "useMarkdownLinks": false\n}\n' > "$obsidian_dir/app.json"
  fi

  # Skip if Obsidian config doesn't exist (Obsidian hasn't been opened yet)
  if [[ ! -f "$obssi_config" ]]; then
    warn "No Obsidian config found at $obssi_config — vault created but not registered in Obsidian."
    info "Open Obsidian manually, then go to File → Open folder as vault and select: $vault_path"
    return 0
  fi

  # Generate a unique ID for this vault (sha256 of path, first 16 chars)
  local id
  id="$(echo "$vault_path" | shasum -a 256 | cut -d' ' -f1 | head -c 16)"

  # Check if already registered
  local existing_path
  existing_path="$(jq -r --arg id "$id" '.vaults[$id].path // ""' "$obssi_config" 2>/dev/null)"
  if [[ -n "$existing_path" ]]; then
    info "Vault already registered in Obsidian (id=$id)"
    return 0
  fi

  # Register the vault in obsidian.json (non-interactive)
  local _obs_tmp="${obssi_config}.tmp.$$"
  if jq --arg id "$id" \
     --arg path "$vault_path" \
     '.vaults[$id] = {"path": $path}' \
     "$obssi_config" > "$_obs_tmp" 2>/dev/null && mv "$_obs_tmp" "$obssi_config"; then
    success "Registered vault in Obsidian (id=$id, path=$vault_path)"
  else
    warn "Failed to register vault in Obsidian."
    info "Open Obsidian manually, then go to File → Open folder as vault and select: $vault_path"
    rm -f "$_obs_tmp"
  fi
}

# ─── Discover Existing Vaults ──────────────────────────────────────────
echo ""
info "Discovering existing Obsidian vaults..."

EXISTS_VAULTS=""
if command -v obsidian &> /dev/null; then
    EXISTS_VAULTS=$(obsidian vaults 2>/dev/null || true)
fi

if [ -n "$EXISTS_VAULTS" ]; then
    success "Found existing vaults:"
    VAULT_NUM=0
    while IFS= read -r line; do
        [ -z "$line" ] && continue
        VAULT_NUM=$((VAULT_NUM + 1))
        echo "   $VAULT_NUM. ${line}"
    done <<< "$EXISTS_VAULTS"
else
    warn "No existing vaults detected (Obsidian may not be running)."
fi

# ─── Mode Selection ────────────────────────────────────────────────────
MODE="${SETUP_MODE:-}"

# Always show guide — useful for both humans and agents
print_guide

# Guard: if no env vars set AND not a TTY, fail with clear error (no hanging)
if [ -z "$MODE" ] && [ ! -t 0 ]; then
    error "No SETUP_MODE set and not running in a terminal."
    info "Agents: use env vars (SETUP_MODE, SETUP_VAULT_NAME) and run non-interactively."
    info "Example: export SETUP_MODE=1 && bash llm-wiki-system-installer/scripts/setup-wizard.sh"
    exit 1
fi

# Support non-interactive mode via environment variables:
#   SETUP_MODE=1|2, SETUP_VAULT_NAME="...", SETUP_VAULT_PATH="/path"

VAULT_NAME="${SETUP_VAULT_NAME:-}"
VAULT_PATH="${SETUP_VAULT_PATH:-}"
CONFIRM="${SETUP_CONFIRM:-y}"

if [ -z "$MODE" ]; then
    echo ""
    info "How would you like to proceed?"
    if [ -n "$EXISTS_VAULTS" ]; then
        echo "   1. Create a NEW vault from scratch"
        echo "   2. Apply to an EXISTING vault (select one above)"
    else
        echo "   1. Create a NEW vault from scratch"
    fi

    echo -n $'\nChoose (1 or 2): ' >&2
    read MODE || true
fi

if [[ "$MODE" != "1" && -z "$EXISTS_VAULTS" ]]; then
    error "No existing vaults available. Creating a new one."
fi

# ─── NEW VAULT MODE ────────────────────────────────────────────────────
if [[ "$MODE" == "1" ]]; then
    if [ -z "$VAULT_NAME" ]; then
        echo -n $'\nEnter vault name (e.g., My Wiki): ' >&2
        read VAULT_NAME || true
    fi

    if [ -z "$VAULT_NAME" ]; then
        error "Vault name cannot be empty."
        exit 1
    fi

    # Resolve vault path — the .llm-wiki folder IS the vault root
    VAULT_PATH="${VAULT_PATH:-}"
    if [ -z "$VAULT_PATH" ]; then
        SETUP_PARENT="$(cd "$SETUP_SRC" && pwd)"
        # Check if llm-wiki-system-installer/ lives inside a .llm-wiki/ folder → use it as vault root
        if [ -d "$SETUP_PARENT/.llm-wiki" ]; then
            VAULT_PATH="$SETUP_PARENT/.llm-wiki"
        else
            # Otherwise create .llm-wiki/ sibling to llm-wiki-system-installer/
            VAULT_PATH="$SETUP_PARENT/../.llm-wiki/$VAULT_NAME"
        fi
    fi

    # Resolve path for display (remove .. segments, normalize)
    VAULT_PATH="$(python3 -c "import os.path; print(os.path.normpath('$VAULT_PATH'))" 2>/dev/null || echo "$VAULT_PATH")"

    # Create the directory if it doesn't exist
    mkdir -p "$VAULT_PATH"

    # Initialize git repo if not already initialized
    if [ ! -d "$VAULT_PATH/.git" ]; then
        info "Initializing git repository..."
        cd "$VAULT_PATH" && git init -q 2>/dev/null || true
    fi

    success "Vault directory: $VAULT_PATH"


# ─── EXISTING VAULT MODE ──────────────────────────────────────────────
elif [[ "$MODE" == "2" ]]; then
    if [ -z "$EXISTS_VAULTS" ]; then
        error "No existing vaults found. Use mode 1 to create a new one."
        exit 1
    fi

    VAULT_NUM=0
    echo -n $'\nSelect vault number: ' >&2
    read VAULT_NUM || true

    if ! [[ "$VAULT_NUM" =~ ^[0-9]+$ ]] || [ "$VAULT_NUM" -lt 1 ] || [ "$VAULT_NUM" -gt "$(echo "$EXISTS_VAULTS" | grep -c .)" ]; then
        error "Invalid selection."
        exit 1
    fi

    VAULT_NAME=$(echo "$EXISTS_VAULTS" | sed -n "${VAULT_NUM}p")
    # For existing vaults, we need the actual path — use obsidian CLI to find it
    VAULT_PATH=$(obsidian vaults 2>/dev/null | sed -n "${VAULT_NUM}p" || true)

    # Fallback: check common locations
    if [ -z "$VAULT_PATH" ]; then
        for base in "$HOME/Obsidian Vault" "$HOME/Documents/Obsidian"; do
            if [ -d "$base/$VAULT_NAME" ]; then
                VAULT_PATH="$base/$VAULT_NAME"
                break
            fi
        done
    fi

    if [ -z "$VAULT_PATH" ] || [ ! -d "$VAULT_PATH" ]; then
        error "Could not resolve path for vault '$VAULT_NAME'. Try mode 1 instead."
        exit 1
    fi

    success "Selected vault: ${VAULT_NAME}"
else
    error "Invalid choice."
    exit 1
fi

# ─── Confirm Before Writing ────────────────────────────────────────────
echo ""
info "This will create the LLM Wiki system in: ${VAULT_PATH}"
echo ""
info "What will be created:"
echo "   Directory structure: Raw/, Wiki/ (Topics, Concepts, Entities, Projects, Logs), Schema/, _templates/, scripts/, .agents/skills/"
echo "   Files: AGENTS.md, welcome note, 7 templates, schema files, wiki_tool.py"
echo "   Pre-commit hook enforcing validation on every commit"

if [ -z "$CONFIRM" ]; then
    echo -n $'\nProceed? (y/n): ' >&2
    read CONFIRM || true
fi

if [[ "$CONFIRM" != "y" && "$CONFIRM" != "Y" ]]; then
    warn "Setup cancelled."
    exit 0
fi

# ─── Setup Function (Self-Contained: copies from bundled llm-wiki-system-installer/ folder) ──
setup_vault() {
    local TARGET_DIR="$1"

    cd "$TARGET_DIR" || exit 1

    # ── Create directory structure
    info "Creating directory structure..."
    mkdir -p Raw/Sources Raw/Files Wiki/{Topics,Concepts,Entities,Projects,Logs} Schema _templates scripts .agents/skills/llm-wiki-ingest .agents/skills/llm-wiki-query .agents/skills/llm-wiki-lint .agents/skills/llm-wiki-maintain .agents/skills/llm-wiki-audit .agents/skills/llm-wiki-setup .agents/skills/llm-wiki-vl

    # ── Create placeholder files
    touch Raw/Sources/.gitkeep Wiki/Topics/.gitkeep Wiki/Concepts/.gitkeep Wiki/Entities/.gitkeep Wiki/Projects/.gitkeep Wiki/Logs/.gitkeep

    # ── Copy system files from bundled setup folder
    info "Copying system files..."

    # Core config (from root of llm-wiki-system-installer/)
    cp "$SETUP_SRC/.gitignore" . 2>/dev/null || true
    cp "$SETUP_SRC/AGENTS.md" . 2>/dev/null || true
    cp "$SETUP_SRC/Welcome.md" . 2>/dev/null || true

    # Templates
    for t in "$SETUP_SRC"/templates/*.md; do
        [ -f "$t" ] && cp "$t" _templates/ 2>/dev/null || true
    done

    # Schema files
    for s in "$SETUP_SRC"/schema/*.md; do
        [ -f "$s" ] && cp "$s" Schema/ 2>/dev/null || true
    done

    # Scripts (wiki_tool.py, wiki_shared.py) — skip setup-wizard.sh
    for s in "$SETUP_SRC"/scripts/*; do
        [ -f "$s" ] && [[ "$(basename "$s")" != "setup-wizard.sh" ]] && cp "$s" scripts/ 2>/dev/null || true
    done

    # Agent skills (one file per skill subdirectory)
    for d in "$SETUP_SRC"/.agents/skills/*/; do
        [ -d "$d" ] && cp "$d"SKILL.md ".agents/skills/$(basename "$d")/" 2>/dev/null || true
    done

    # Pre-commit hook
    mkdir -p .git/hooks 2>/dev/null || true
    # Install git hooks
    mkdir -p .git/hooks 2>/dev/null || true
    for hook in pre-commit pre-push; do
        if [ -f "$SETUP_SRC"/hooks/$hook ]; then
            cp "$SETUP_SRC"/hooks/$hook .git/hooks/$hook 2>/dev/null || true
            chmod +x .git/hooks/$hook 2>/dev/null || true
        fi
    done

    success "Setup complete: $TARGET_DIR"

    # Register vault with Obsidian (so obsidian CLI discovers it)
    _register_obsidian_vault "$TARGET_DIR"
}

# ─── Run Setup ────────────────────────────────────────────────────────
setup_vault "$VAULT_PATH"

# ─── Clean up llm-wiki-system-installer/ if it's inside the vault parent folder ─────
clean_up_installer() {
    local SETUP_PARENT="$(cd "$SETUP_SRC" && pwd)"
    local PARENT_DIR=$(dirname "$SETUP_PARENT")
    for dir in LLM-wiki-system-install installer setup; do
        if [ -d "$PARENT_DIR/$dir" ]; then
            rm -rf "$PARENT_DIR/$dir"
            success "Cleaned up: $dir/ (installation complete)"
        fi
    done
}
clean_up_installer
