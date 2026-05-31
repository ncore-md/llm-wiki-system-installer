---
name: llm-wiki-ingest
description: Process raw content (URLs, markdown files, images) into structured wiki notes. Use when the user provides a source to ingest or asks to process unprocessed files.
compatibility: Python 3.8+, Obsidian running with CLI enabled, Chrome DevTools Protocol access
metadata:
  category: wiki-ingest
---

## When triggered
**Invoking this skill means executing the workflow, not discussing it.** The very first action is vault selection.

**Check for a vault name in the invocation arguments (text after the `<skill>` block).** If one was provided, use it directly. Otherwise, list available vaults and ask the user to choose.

Do not describe, explain, or summarize the skill before performing this step.

## When to use
The user adds a new source, wants to process raw content into wiki notes, or asks you to create/update compiled Wiki notes.

## Prerequisites
- **Obsidian must be running** — all vault operations use the Obsidian CLI which connects via Chrome DevTools Protocol
- **Vault must be identified before any operation** — see Vault Selection below


## Shared Infrastructure

**Pre-flight Check and Vault Selection are handled by the shared infrastructure.** See `references/shared-infra.md` for details.


## Reference Files

Detailed workflow steps and operations are in reference files:

- **`references/vault-operations.md`** — Config Discovery, Vault Operations (obsidian CLI usage)
- **`references/workflow-steps.md`** — Detailed workflow steps (Steps 0–9)
- **`references/sources-reference.md`** — Sources manifest, Step 5 (image processing), Steps 6–9

## Workflow Overview

Execute the workflow steps in order. Each step has a mandatory checklist — verify completion before proceeding to the next.

**See `references/workflow-steps.md` for detailed step-by-step instructions.**
## Reference
- `AGENTS.md` — Ingest Workflow section, Core Rules, directory structure (at wiki root)
- `_templates/*.md` — frontmatter schemas for each note type
- `scripts/wiki_tool.py` — build, lint, search-catalog, source-scan, log
- `scripts/wiki_shared.py` — shared utilities: config discovery (`config`, `discover-config`), project config discovery (`find_project_config`, `load_project_config`), VL discovery (`discover`), model resolution (`models <task>`), defaults/overrides CLI
- `llm-wiki-setup` skill — invoked via subagent tool with `skill: "llm-wiki-setup"` when config is missing
- `.llm-wiki-config/config.json` — project-level vault declarations and permissions (source of truth)
- `Schema/.llm-wiki-cache.json` — per-project shared cache (defaults, VL discovery results, task overrides, config)

## Error Handling

- **Vault selection fails** — If `obsidian list-vaults` returns no vaults or errors, run setup first (call llm-wiki-setup)
- **Obsidian CLI connection fails** — Verify Obsidian is running and the Chrome DevTools Protocol port is accessible. If it times out, wait 10s and retry once
- **Image processing fails** — If Defuddle CLI or vision model returns an error, log the failure and continue with non-image sources. Do not block the entire ingest
- **Git commit conflicts** — If `git add` or `commit` fails due to unstaged changes, abort and report the conflict. Do not force-push or overwrite local work
- **File write errors** — If a file cannot be written (permissions, locked), report the specific path and abort. Do not skip affected files silently
- **Config missing or corrupted** — If `.llm-wiki-config/config.json` is absent, malformed JSON, or has no vaults listed: call llm-wiki-setup before proceeding

## What Not to Do (Anti-Patterns)

- **Do not skip vault selection** — Every operation requires an explicit vault. Never guess or default to a directory
- **Do not process images as text** — Use Defuddle CLI for web pages and vision model for screenshots. Never paste image content directly as text
- **Do not overwrite existing compiled notes** — Use the manifest to detect duplicates. Create new notes or append; never blindly overwrite
- **Do not commit without the pre-commit hook** — The hook runs lint and source checks. Skip only if explicitly told to
- **Do not ignore defuddle errors** — If a URL fails, report it and move to the next source. Do not fake content
- **Do not create notes without frontmatter** — Every note must have `title`, `tags`, and at least one source
