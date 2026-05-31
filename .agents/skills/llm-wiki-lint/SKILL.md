---
name: llm-wiki-lint
description: Validate wiki notes for schema compliance. Use when user asks to check quality, before committing changes, or after creating/editing notes.
compatibility: Python 3.8+, Chrome DevTools Protocol access, config.json present
metadata:
  category: wiki-quality
---

## When to use
The user asks to check wiki quality, before committing changes that affect Wiki notes, or after creating/editing a note.

## Prerequisites
- **Vault must be identified before any operation** — see Vault Selection below.


## Shared Infrastructure

**Pre-flight Check and Vault Selection are handled by the shared infrastructure.** See `references/shared-infra.md` for details.

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
   This validates raw source frontmatter (title, reference/source present, created date format) and coverage state: processed sources must have `covered_by` entries that actually exist on disk. Stale or missing coverage is reported as errors.

7. **Report any issues** found with file names and specific violations. Fix lint failures before committing — never commit past a failed lint.

## Error Handling

- **Vault selection fails** — If `obsidian list-vaults` returns no vaults, run llm-wiki-setup first
- **Obsidian CLI connection fails** — Verify Obsidian is running. Retry once after 10s, then report
- **Config missing** — If `.llm-wiki-config/config.json` is absent, run llm-wiki-setup first
- **Lint tool errors** — If `wiki_tool.py lint` crashes, report the error and continue with manual checks
- **Schema validation errors** — If a note has invalid frontmatter, report the exact field and line. Do not auto-correct

## What Not to Do (Anti-Patterns)

- **Do not skip source_count validation** — This is the most critical check. Verify it always equals `sources` array length
- **Do not auto-fix frontmatter** — Report violations but do not edit YAML directly. Let the user or maintainer fix issues
- **Do not treat warnings as errors** — Warnings (missing dates, extra fields) should be reported but do not block commits
- **Do not ignore source-lint results** — Raw sources must have title, reference/source, and created date. Flag all missing fields
