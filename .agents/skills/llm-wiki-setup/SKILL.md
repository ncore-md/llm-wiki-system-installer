---
name: llm-wiki-setup
description: Create .llm-wiki-config/config.json for first-time wiki setup. Use when config is missing, on first run, or user wants to add/change vaults.
compatibility: Python 3.8+, Obsidian running with CLI enabled, Chrome DevTools Protocol access
metadata:
  category: wiki-setup
---

## When triggered
**Invoking this skill means executing the setup workflow, not discussing it.** The very first action is checking for an existing project config.

**Do not describe, explain, or summarize the skill before performing this step.**

## When to use
The first time a wiki skill runs in a project, or when `.llm-wiki-config/config.json` is missing. This skill sets up the project configuration so other skills can operate.

**Never skip setup.** Without a config file, no vaults are known and no wiki operations can proceed.

## Prerequisites
- **Obsidian must be running** — the setup uses `obsidian vaults --verbose` to discover available vaults
- **Run from wiki root or project directory** — the skill walks up to find `.llm-wiki/` and `Wiki/ + Schema/`

## Workflow
1. **Check for existing project config:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_shared.py find-project-config 2>&1
   ```
   Output will be the path to `.llm-wiki-config/` or `not found`.

   **If `.llm-wiki-config/config.json` does NOT exist:** proceed to step 2 (full setup flow).

   If `.llm-wiki-config/config.json` exists, read and display it to the user. Ask: "Config already exists at <path>. What would you like to do?"
   - **Add vaults:** discover Obsidian vaults and add new ones (go to step 2, then modify existing config — see "Updating Existing Config" below)
   - **Edit permissions:** change a vault's role (go to step 3, then rewrite config)
   - **Change raw_paths:** modify or add source directories (go to step 4, then rewrite config)
   - **Update defaults:** change ingest vault, text/VL model settings (go to step 5)
   - **Recreate from scratch:** discard current config and start over (go to step 2)
   - **Done/Exit:** no changes needed, exit

   **Updating existing config (partial edits):** When modifying an existing file rather than recreating it, read the current JSON with Python, modify in-memory, then write back. **Important:** `wiki_shared.py config` caches discovery results — after modifying the file, either clear the cache (`rm Schema/.llm-wiki-cache.json`) or always use `--force` flag to force re-reading the config file.
   ```bash
   python3 << 'PYEOF'
import json, os

config_path = "<project-root>/.llm-wiki-config/config.json"
with open(config_path) as f:
    config = json.load(f)

# Example: add a new vault
config["vaults"]["NewVault"] = {
    "wiki_root": "/path/to/NewVault/.llm-wiki/NewVault",
    "permissions": ["read"],
    "raw_paths": []
}

# Example: modify a vault's raw paths
config["vaults"]["Core"]["raw_paths"] = ["/new/path/to/Raw/Sources"]

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print("Config updated.")
PYEOF
   ```

2. **Discover available Obsidian vaults:**
   ```bash
   obsidian vaults --verbose 2>&1 | head -30
   ```

   Present the list to the user:
   ```
   Available Obsidian vaults:
     1. Core       — /path/to/Core/.llm-wiki/Core
     2. NLite      — /path/to/NLite
     ...

   Which vaults do you want this project to access? (Type numbers separated by spaces, or 'all' for all.)
   ```

3. **Select vaults and assign permissions:** For each selected vault, determine its role:

   | Vault Role | Permissions | Notes |
   |---|---|---|
   | **Primary wiki** (main knowledge base) | `read, write, ingest, maintain` | The vault you'll actively create/update notes in |
   | **Read-only reference** | `read` | Used for lookups only (e.g., competitor analysis) |
   | **Disabled** | — | Skip entirely |

   Ask the user for each vault:
   ```
   Vault: Core
     Role? (primary / read-only) → primary

   Vault: NLite  
     Role? (primary / read-only) → read-only
   ```

4. **Configure raw source paths:** For each writable vault (those with `write` or `ingest` permission), ask the user to specify its raw source directories. Raw paths are **flat** — no auto-discovery, no convention assumptions.

   Ask the user for each writable vault:
   ```
   Vault: Core (primary)
     Raw source directories? (Enter paths, one per line. Empty = no raw sources.)
     > Raw/Sources
     > /Users/bernardoresende/Core/.llm-wiki/Core/Raw/Files
     > (empty to stop)
   ```

   Resolve relative paths against the wiki root using `os.path.abspath()`. For read-only vaults (`read` only), skip raw paths — set `raw_paths: []`. These are stored in config as absolute paths.

   Example path resolution:
   ```bash
   python3 << 'PYEOF'
import os, json

wiki_root = "/Users/bernardoresende/Core/.llm-wiki/Core"
user_inputs = ["Raw/Sources", "Raw/Files"]  # from user input
raw_paths = [os.path.abspath(p) if not os.path.isabs(p) else p for p in user_inputs]

print("Resolved paths:")
for rp in raw_paths:
    print(f"  {rp}")

# Store in config
config_path = "/Users/bernardoresende/Core/.llm-wiki-config/config.json"
with open(config_path) as f:
    config = json.load(f)
config["vaults"]["Core"]["raw_paths"] = raw_paths
with open(config_path, "w") as f:
    json.dump(config, f, indent=2)
print("Config updated with resolved paths.")
PYEOF
   ```

   **⚠️ Limitation:** `get_raw_sources()` in wiki_tool.py only scans the first configured raw path using flat `os.listdir()` (no recursion into subdirectories, no multi-dir support). Only configure one raw path per vault unless you're certain the wiki tool will be updated to handle multiple.

5. **Set vault rules file path:** Ask the user for each vault's rules file — where note conventions (key point limits, required sections) are defined. Default is `AGENTS.md` at the vault root.
   ```
   Vault: Core
     Rules file? (relative path from wiki root, default AGENTS.md)
     > AGENTS.md
   ```
   Store as: `rules_path: { relative: "AGENTS.md", absolute: "$WIKI_ROOT/AGENTS.md" }`
   Accept custom paths (e.g., `VaultRules.md`) or press Enter for default.

6. **Set defaults:** Ask about default settings:

   a. **Default ingest vault** (where new content goes by default):
      - If only one vault is selected → use it automatically, no prompt needed.
      - If multiple vaults → ask the user: `Which vault should be the default for ingest operations? (Type name or number)`

   b. **Text model** (for note generation):
      ```bash
      python3 scripts/wiki_shared.py set-default text_model_id "model-id" 2>&1
      ```

   c. **VL model** (for image analysis — optional):
      Ask the user for VL settings:
        - Provider: e.g., `omlx`, `openai`
        - Model ID: e.g., `qwen3.6-35b-a3b-mlx-vl-oQ4-FP16`
        - Base URL: e.g., `http://localhost:8000/v1`
      Write VL settings to project config (not just cache).
      **Cache note:** This modifies the file in-place — clear `Schema/.llm-wiki-cache.json` or use `--force` on subsequent reads.
      ```bash
      python3 << 'PYEOF'
import json, os

config_path = "<project-root>/.llm-wiki-config/config.json"
with open(config_path) as f:
    config = json.load(f)

defaults = config.setdefault("defaults", {})
defaults["vl_provider"] = "<provider>"
defaults["vl_model_id"] = "<model-id>"
defaults["vl_base_url"] = "<base-url>"

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print("VL settings written to project config.")
PYEOF
      ```

7. **Write config file:** Create `.llm-wiki-config/config.json` at the project root (walk up from wiki root):

   ```json
   {
     "wiki_path": "/Users/bernardoresende/Core/.llm-wiki",

     "vaults": {
       "Core": {
         "wiki_root": "/Users/bernardoresende/Core/.llm-wiki/Core",
         "permissions": ["read", "write", "ingest", "maintain"],
         "raw_paths": ["/Users/bernardoresende/Core/.llm-wiki/Core/Raw/Sources"],
         "rules_path": {
           "relative": "AGENTS.md",
           "absolute": "/Users/bernardoresende/Core/.llm-wiki/Core/AGENTS.md"
         }
       },
       "NLite": {
         "wiki_root": "/path/to/NLite/.llm-wiki/NLite",
         "permissions": ["read"],
         "raw_paths": []
       }
     },

     "defaults": {
       "ingest_vault": "<primary-vault-name>",
       "text_model_id": "<model-id-or-null>",
       "vl_provider": "omlx",
       "vl_model_id": "<model-id-or-null>",
       "vl_base_url": "http://localhost:8000/v1"
     }
   }
   ```

   **`wiki_root`:** Absolute path to each vault's wiki root directory (where `AGENTS.md`, `_templates/`, `Wiki/`, `Schema/` live).
   **raw_paths:** Paths to raw source directories. Both relative and absolute paths are accepted — normalize with `os.path.abspath()` before writing.

   Use Python to write the file (creates directory if needed).
   **Cache note:** If updating an existing config, clear `Schema/.llm-wiki-cache.json` or use `--force` on subsequent reads.
   ```bash
   python3 << 'PYEOF'
import json, os

config_path = "<project-root>/.llm-wiki-config/config.json"
os.makedirs(os.path.dirname(config_path), exist_ok=True)

config = { ... }  # Fill from steps above

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print(f"Config written to {config_path}")
PYEOF
   ```

8. **Validate and cache:** After writing, validate the config:

   a. **Verify config is readable:**
      ```bash
      cd <wiki-root> && python3 scripts/wiki_shared.py config 2>&1 | head -20
      ```

   b. **Run wiki discovery to populate cache (also discovers tag routing):**
      ```bash
      cd <wiki-root> && python3 scripts/wiki_shared.py discover --force 2>&1
      ```
      Discovers tag routing, raw source dirs, and populates vault config in the shared cache.

   c. **Verify raw_paths are populated for write/ingest vaults:**
      ```bash
      cd <wiki-root> && python3 scripts/wiki_shared.py config --force 2>&1 | grep raw_paths
      ```
      Should show absolute paths, e.g. `raw_paths: [/path/to/Raw/Sources]`.

   d. **Verify all declared vaults are accessible:**
      ```bash
      obsidian vaults --verbose 2>&1 | grep -i "<vault-name>"
      ```

   Report success: "Project config created at <path>. Vault declarations: [list]. You can now use wiki skills."

## Validation Rules
- **vaults** must be a non-empty mapping of vault names to permission objects
- Each vault's **permissions** must be a list containing only: `read`, `write`, `ingest`, `maintain`
- **wiki_path** should point to the parent `.llm-wiki/` directory (or directly to a wiki root)
- **defaults.ingest_vault** must match one of the declared vault names

## Error Handling
- If Obsidian CLI fails: "Obsidian is not running or the CLI cannot connect. Please start Obsidian and try again."
- If config write fails: "Could not create .llm-wiki-config/. Please check permissions."
- If a declared vault doesn't exist in Obsidian: "Vault '<name>' was declared but is not found in Obsidian. Remove it or check the name."

## Reference
- `.llm-wiki-config/config.json` — project-level vault declarations and permissions (source of truth)
- `scripts/wiki_shared.py` — shared utilities: config discovery (`config`, `discover-config`), project config discovery (`find_project_config`, `load_project_config`)
- `<wiki-root>/AGENTS.md` — Core Rules, directory structure
