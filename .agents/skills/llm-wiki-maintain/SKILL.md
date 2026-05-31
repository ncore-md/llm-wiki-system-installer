---
name: llm-wiki-maintain
description: Full wiki health cycle: doctor → build → lint → source-lint. Use before meaningful commits or when user asks for maintenance.
compatibility: Python 3.8+, Chrome DevTools Protocol access, config.json present
metadata:
  category: wiki-quality
---

## When to use
Before a meaningful commit that touches Wiki content, or when the user asks you to run maintenance on the wiki.

## Prerequisites
- **Vault must be identified before any operation** — see Vault Selection below.


## Shared Infrastructure

**Pre-flight Check and Vault Selection are handled by the shared infrastructure.** See `references/shared-infra.md` for details.

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
   Validates processed sources have valid wiki coverage (entries in `covered_by` must exist on disk). Run `source-scan --update --accept-covered` to clean up stale entries if lint fails.

6. **Log changes** if the maintenance cycle modified Wiki content:
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py log --title "..." --details "..."
   ```

7. **Report results** — all checks must pass before committing. If any fail, fix the issues first.

## Error Handling

- **Vault selection fails** — If `obsidian list-vaults` returns no vaults, run llm-wiki-setup first
- **Obsidian CLI connection fails** — Verify Obsidian is running. Retry once after 10s, then report
- **Config missing** — If `.llm-wiki-config/config.json` is absent, run llm-wiki-setup first
- **Doctor reports unrecoverable errors** — If the doctor finds a broken config or missing core files, abort and report
- **Build fails mid-cycle** — If the build process crashes on a specific note, skip it and continue. Report which notes were skipped

## What Not to Do (Anti-Patterns)

- **Do not skip the full cycle** — Doctor → build → lint → source-lint must all run. Do not skip steps for "speed"
- **Do not force-sync without doctor** — The doctor check validates vault health before any sync. Never skip it
- **Do not overwrite user edits** — If a compiled note differs between source and Obsidian, report the conflict. Do not blindly overwrite
- **Do not ignore lint failures during maintenance** — If lint finds issues, fix them or report them. Do not proceed to commit
