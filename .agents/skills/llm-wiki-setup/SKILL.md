---
name: llm-wiki-setup
description: Set up the LLM Wiki project config when no .llm-wiki-config/config.json exists. Uses Obsidian CLI and obsidian skills to discover available vaults, then guides the user through declaring them with permissions.
---

## When triggered
**Invoking this skill means executing the setup workflow, not discussing it.** The very first action is checking for an existing project config.

**Do not describe, explain, or summarize the skill before performing this step.**

## When to use
The first time a wiki skill runs in a project, or when `.llm-wiki-config/config.json` is missing. This skill sets up the project configuration so other skills can operate.

**Never skip setup.** Without a config file, no vaults are known and no wiki operations can proceed.

## Prerequisites
- **Obsidian must be running** — the setup uses `obsidian vaults --verbose` to discover available vaults
- **Run from project directory** — the skill creates a project-local config at `<project>/.llm-wiki-config/config.json`. With independent vaults, the vault lives elsewhere (e.g. `~/.llm-wiki-vaults/`), and the project config declares vault access.

## Workflow
1. **Check for existing project config (LOCAL ONLY):**
   ```bash
   cd <project-root> && test -f .llm-wiki-config/config.json && echo "exists" || echo "missing"
   ```
   This checks the project directory for a local `.llm-wiki-config/config.json`.

   **If `.llm-wiki-config/config.json` exists in this project:** read and display it to the user. Ask: "Config already exists at <path>. What would you like to do?"
   - **Add vaults:** discover Obsidian vaults and add new ones (go to step 2, then modify existing config — see "Updating Existing Config" below)
   - **Edit permissions:** change a vault's role (go to step 3, then rewrite config)
   - **Change raw_paths:** modify or add source directories (go to step 4, then rewrite config)
   - **Update defaults:** change ingest vault, text/VL model settings (go to step 5)
   - **Done/Exit:** no changes needed, exit

   **If `.llm-wiki-config/config.json` does NOT exist in this project:** proceed to step 2 (full setup flow to create one). Do NOT search upward for ancestor project configs — each project has its own isolated config.

   **Updating existing config (partial edits):** When modifying an existing file rather than recreating it, read the current JSON with Python, modify in-memory, then write back. **Important:** `wiki_shared.py config` caches discovery results — after modifying the file, either clear the cache (`rm Schema/.llm-wiki-cache.json`) or always use `--force` flag to force re-reading the config file.
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
config["vaults"]["<primary-vault-name>"]["raw_paths"] = ["/new/path/to/Raw/Sources"]

with open(config_path, "w") as f:
    json.dump(config, f, indent=2)

print("Config updated.")
PYEOF
   ```

2. **Discover vaults and auto-select:**
   ```bash
   obsidian vaults --verbose 2>&1 | head -30
   ```

   **Auto-selection:** If there's exactly 1 vault → select it as primary. If multiple → select all, first as primary, rest as read-only.

   Present the auto-selection and ask for confirmation. User can reject to manually choose.

3. **Auto-detect raw source paths:** For each writable vault, scan for `Raw/Sources/`:
   ```bash
   ls <wiki-root>/Raw/Sources && echo "found"
   ```
   If found → use it. If not → ask user (with `Raw/Sources` as default).

4. **Auto-detect models:** Check existing config defaults, then `wiki_shared.py discover` for VL models, then `~/.pi/agent/models.json` for text models. Only ask the user if discovery finds nothing.

5. **Rules file:** Default is `AGENTS.md` at vault root. Only ask if user wants a custom path.

6. **Set defaults:**
   - Ingest vault: auto-select first/only vault if single choice
   - Text model: from config defaults or discovery
   - VL model: from config defaults or `wiki_shared.py discover`

7. **Write config file:** Create `.llm-wiki-config/config.json` at the project root (walk up from wiki root):

   ```json
   {
     "wiki_path": "<project-root>",

     "vaults": {
       "<primary-vault-name>": {
         "wiki_root": "<primary-wiki-root>",
         "permissions": ["read", "write", "ingest", "maintain"],
         "raw_paths": ["<primary-wiki-root>/Raw/Sources"],
         "rules_path": {
           "relative": "AGENTS.md",
           "absolute": "<primary-wiki-root>/AGENTS.md"
         }
       },
       "<secondary-vault-name>": {
         "wiki_root": "<secondary-wiki-root>",
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
