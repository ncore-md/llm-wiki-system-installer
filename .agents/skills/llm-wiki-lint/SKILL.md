---
name: llm-wiki-lint
description: Check wiki note quality, validate frontmatter, and run linting before commits.
---

## When to use
The user asks to check wiki quality, before committing changes that affect Wiki notes, or after creating/editing a note.

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

**FIRST ACTION: Before performing ANY step, identify which vault to lint.**

1. **If the user explicitly named a vault** (e.g., "lint Core", `/llm-wiki-lint Core`), use that name directly.
2. **Otherwise, use the list from Pre-flight Check** (already ran `wiki_shared.py vaults`). Present it and ask: "Available vaults (from project config): [list]. Which one do you want to lint?"

3. **Validate** — confirm the selected vault is in the list from Pre-flight Check.

**Once identified, use that exact vault name for every `obsidian` command.**

## Reference
- `<wiki-root>/AGENTS.md` — Core Rules (Non-Negotiable), Allowed Tags section, directory structure
- `.llm-wiki-config/config.json` — project-level vault declarations (source of truth)
- `<wiki-root>/Schema/frontmatter-schema.md` — frontmatter field requirements
- `<wiki-root>/Schema/lint-checklist.md` — lint checklist
- `<wiki-root>/scripts/wiki_tool.py` — lint, source-lint commands

**How to find the wiki root:** Once you have a vault name from Vault Selection above, use project config or auto-detect:
```bash
cd <wiki-root> && python3 scripts/wiki_shared.py config 2>&1 | grep wiki_path
```
The wiki root is at the path declared in `.llm-wiki-config/config.json` under `wiki_path`, or auto-detected from Wiki/ + Schema/ directories.

## Workflow
1. **Identify the wiki root** for the selected vault (see Reference above).

2. **Read AGENTS.md** from the wiki root to get:
   - Allowed tags for compiled notes (from "Allowed Tags" section)
   - Required frontmatter fields (from Schema/frontmatter-schema.md)
   - Structured rules from `---checklist---` section (key point limits, required sections, etc.) via:
     ```bash
     cd <wiki-root> && python3 -c "
import json, sys; sys.path.insert(0, 'scripts')
from wiki_shared import parse_rules
rules = parse_rules('$WIKI_ROOT')
print(json.dumps(rules, indent=2))"
     ```

3. **Check frontmatter on each Wiki note:**
   - `tags` array exists and contains one of the allowed tags for compiled notes (from AGENTS.md — NOT hardcoded)
   - `topics` and `sources` arrays are present (even if empty: `[]`)
   - Dates (`created`, `updated`) in YYYY-MM-DD format

4. **Check source_count:** must equal the number of entries in `sources` array (derived, not manually set)

5. **Run programmatic validation:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py lint
   ```

6. **Run source coverage check:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py source-lint
   ```

7. **Report any issues** found with file names and specific violations. Fix lint failures before committing — never commit past a failed lint.
