## Pre-flight Check (Required Before Vault Selection)

**Before attempting vault selection, verify config is usable.** If it's missing or empty, offer setup.

1. **Check vaults:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_shared.py vaults 2>&1
   ```

2. **If output lists vaults** (e.g., `Core [read,write,...]`): proceed to Vault Selection.

3. **If output is empty or says "No project config":**
   - Tell the user: "Config not found or has no vaults declared (.llm-wiki-config/config.json). Without it, wiki operations can't proceed."
   - Ask: "Would you like to run the setup wizard? It will discover your Obsidian vaults and let you assign permissions (read, write, ingest, maintain)."
   - **If user agrees:** spawn a subagent to run setup:
     ```javascript
     subagent({{
       agent: "scout",
       task: "Run the llm-wiki-setup workflow to create .llm-wiki-config/config.json. Walk up from wiki root, discover vaults via obsidian CLI, guide user through permission selection, write config file.",
       skill: "llm-wiki-setup"
     }})
     ```
   - **If user declines:** stop and explain wiki operations require a project config.

## Vault Selection (Required Before Any Operation)

This skill is **vault-agnostic**. It works with any Obsidian vault that contains an LLM Wiki structure.

**FIRST ACTION: Before performing ANY step, identify which vault to operate on.**

1. **If the user explicitly named a vault** (e.g., "audit Core", `/llm-wiki-audit Core`), use that name directly.

2. **Otherwise, use the list from Pre-flight Check** (already ran `wiki_shared.py vaults`). Present it and ask: "Available vaults (from project config): [list]. Which one do you want to audit?"

3. **Validate** — confirm the selected vault is in the list from Pre-flight Check.

4. **How to find the wiki root:** Once you have a vault name from Vault Selection above, use project config or auto-detect:
   - The wiki root is the directory containing `.llm-wiki-config/config.json` (usually a parent of the vault)
   - Use `wiki_shared.py resolve-path <vault-name>` to find it:
     ```bash
     cd <wiki-root> && python3 scripts/wiki_shared.py resolve-path Core
     ```

5. **Once identified, use that exact vault name for every `obsidian` command.** Never guess or change the vault mid-operation.

6. **The `<wiki-root>` placeholder** in all subsequent commands refers to the directory containing `.llm-wiki-config/config.json`, NOT the vault's root.

## Vault Isolation Rule (Required Before Moving to Next Vault)

After processing each vault, CLEAR ALL config-derived variables before moving to the next.
The project config file (`.llm-wiki-config/config.json`) is shared across all vaults —
variables set for one vault must not be reused when processing another.

**Variables to clear:** `RAW_PATH`, `WIKI_FOLDER`, `TEMPLATES_DIR`, `TAG_ROUTING`,
`__WIKI_DIR__`, `__RAW_PATHS__`, topic title lists, catalog search results.

**Before processing the next vault:**
1. Extract the new vault's settings from config (use `wiki_shared.py resolve-path <vault-name>`
   to get its `wiki_root` and raw paths — do NOT reuse previous vault's values)
2. Re-collect topic titles from the NEW vault's `catalog.jsonl` (read from its own wiki_root,
   not a previously cached path)
3. Re-scan raw paths from the NEW vault's config entry (do not reuse previous scan results)

**Verification:** Before writing any note, confirm the target path exists within
the current vault's `wiki_root`. If a path does not resolve, abort and report — do NOT guess.
