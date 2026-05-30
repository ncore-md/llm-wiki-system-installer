---
name: llm-wiki-query
description: Search and query the Wiki knowledge base to answer user questions from compiled notes.
---

## When to use
The user asks a question that could be answered from the Wiki knowledge base, or wants you to look up something in the wiki.

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

**FIRST ACTION: Before performing ANY step, identify which vault to query.**

1. **If the user explicitly named a wiki** (e.g., "search Core wiki", `/llm-wiki-query Core`), use that name.
2. **Otherwise, use the list from Pre-flight Check** (already ran `wiki_shared.py vaults`). Present it and ask: "Available vaults (from project config): [list]. Which wiki do you want to search?"

3. **Validate** — confirm the selected vault is in the list from Pre-flight Check.

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
