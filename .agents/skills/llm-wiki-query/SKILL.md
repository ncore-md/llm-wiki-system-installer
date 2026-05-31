---
name: llm-wiki-query
description: Answer questions using wiki's compiled knowledge. Search catalog first, synthesize from compiled notes. Use when user asks something potentially answerable from Wiki.
compatibility: Python 3.8+, Chrome DevTools Protocol access, config.json present
metadata:
  category: wiki-query
---

## When to use
The user asks a question that could be answered from the Wiki knowledge base, or wants you to look up something in the wiki.

## Prerequisites
- **Vault must be identified before any operation** — see Vault Selection below.


## Shared Infrastructure

**Pre-flight Check and Vault Selection are handled by the shared infrastructure.** See `references/shared-infra.md` for details.

## Reference
- `<wiki-root>/AGENTS.md` — Query Workflow section, Core Rules
- `.llm-wiki-config/config.json` — project-level vault declarations (source of truth)
- `<wiki-root>/Wiki/index.md` — compiled knowledge base overview (always check first)
- `<wiki-root>/scripts/wiki_tool.py` — search-catalog command

**How to find the wiki root:** Once you have a vault name, use project config or auto-detect:
```bash
cd <wiki-root> && python3 scripts/wiki_shared.py config 2>&1 | grep wiki_path
```
The wiki root is at the path declared in `.llm-wiki-config/config.json` under `wiki_path`, or auto-detected from Wiki/ + Schema/ directories.

## Workflow
1. **Identify the wiki root** for the selected vault (see Reference above).

2. **Start with `<wiki-root>/Wiki/index.md`** for an overview of available topics and concepts.

3. **Search the catalog:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py search-catalog --query "user topic"
   ```

4. **Open the most relevant Wiki notes** from Step 3 results — not all Raw context. Focus on top matches only.

5. **Synthesize an answer** from the compiled notes (distilled knowledge). Prefer compiled Wiki notes over raw source material.

6. **Open Raw sources only when:**
   - The compiled note is insufficient, OR
   - Source-level verification is requested.

7. **Cite both** the compiled note and Raw source when your answer depends on source material.

## Core Rules During Query
- Always search the catalog before reading Raw sources directly.
- Prefer compiled Wiki notes over raw source material — they are pre-distilled and structured.
- If the catalog returns no results, inform the user that the topic may not be in this wiki yet.
- Never invent information — only report what is found in the notes or sources.

## Error Handling

- **Vault selection fails** — If `obsidian list-vaults` returns no vaults, run llm-wiki-setup first
- **Obsidian CLI connection fails** — Verify Obsidian is running. Retry once after 10s, then report
- **Config missing** — If `.llm-wiki-config/config.json` is absent, run llm-wiki-setup first
- **Catalog search returns no results** — Inform the user that the topic may not be in the wiki. Suggest adding it via ingest
- **Note read fails** — If a note cannot be opened (missing, corrupted), skip it and report. Do not fabricate content

## What Not to Do (Anti-Patterns)

- **Do not invent information** — Only report what is found in wiki notes or sources. Never hallucinate answers
- **Do not skip catalog search** — Always query the catalog first before reading Raw sources directly
- **Do not read all notes for every query** — Use the catalog to narrow down relevant sources. Reading everything is wasteful and slow
- **Do not expose raw source content without context** — When citing sources, explain what they contribute to the answer
- **Do not mix compiled and raw without distinction** — Clearly state whether your answer comes from a compiled note or a Raw source
