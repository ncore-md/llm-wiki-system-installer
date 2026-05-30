---
name: llm-wiki-maintain
description: Run maintenance checks on the wiki — health, rebuild, lint, and source coverage.
---

## When to use
Before a meaningful commit that touches Wiki content, or when the user asks you to run maintenance on the wiki.

## Prerequisites
- **Vault must be identified before any operation** — see Vault Selection below.

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
     subagent({
       agent: "scout",
       task: "Run the llm-wiki-setup workflow to create .llm-wiki-config/config.json. Walk up from wiki root, discover vaults via obsidian CLI, guide user through permission selection, write config file.",
       skill: "llm-wiki-setup"
     })
     ```
   - **If user declines:** stop and explain wiki operations require a project config.

## Vault Selection (Required Before Any Operation)
This skill is **vault-agnostic**. It works with any Obsidian vault that contains an LLM Wiki structure.

**FIRST ACTION: Before performing ANY step, identify which vault to maintain.**

1. **If the user explicitly named a vault** (e.g., "maintain Core", `/llm-wiki-maintain Core`), use that name.
2. **Otherwise, use the list from Pre-flight Check** (already ran `wiki_shared.py vaults`). Present it and ask: "Available vaults (from project config): [list]. Which one do you want to maintain?"

3. **Validate** — confirm the selected vault is in the list from Pre-flight Check.

## Reference
- `<wiki-root>/AGENTS.md` — Maintenance Gate section, Ingest Workflow step 7
- `.llm-wiki-config/config.json` — project-level vault declarations (source of truth)
- `<wiki-root>/scripts/wiki_tool.py` — all commands

**How to find the wiki root:** Once you have a vault name, use project config or auto-detect:
```bash
cd <wiki-root> && python3 scripts/wiki_shared.py config 2>&1 | grep wiki_path
```
The wiki root is at the path declared in `.llm-wiki-config/config.json` under `wiki_path`, or auto-detected from Wiki/ + Schema/ directories.

## Workflow
1. **Identify the wiki root** for the selected vault (see Reference above).

2. **Run health check:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py doctor
   ```

3. **Rebuild catalog and index:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py build
   ```

4. **Validate compiled notes:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py lint
   ```

5. **Check Raw source coverage:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py source-lint
   ```

6. **Log changes** if the maintenance cycle modified Wiki content:
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py log --title "..." --details "..."
   ```

7. **Report results** — all checks must pass before committing. If any fail, fix the issues first.
