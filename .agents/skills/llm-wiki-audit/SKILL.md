---
name: llm-wiki-audit
description: Security and compliance audit for the wiki repository. Scans for secrets, broken references, orphaned notes, and data exposure risks.
---

## When to use
Before pushing changes to a public repository, or when the user asks about security compliance.

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

**FIRST ACTION: Before performing ANY step, identify which vault to audit.**

1. **If the user explicitly named a vault** (e.g., "audit Core", `/llm-wiki-audit Core`), use that name directly.
2. **Otherwise, use the list from Pre-flight Check** (already ran `wiki_shared.py vaults`). Present it and ask: "Available vaults (from project config): [list]. Which one do you want to audit?"

3. **Validate** — confirm the selected vault is in the list from Pre-flight Check.

## Reference
- `<wiki-root>/AGENTS.md` — Core Rules, when to run audit
- `.llm-wiki-config/config.json` — project-level vault declarations (source of truth)
- `.llm-wiki-config/audit-rules.json` — configurable audit patterns (optional, uses defaults if missing)
- `<wiki-root>/scripts/wiki_tool.py` — `audit`, `security-scan` commands

**How to find the wiki root:** Once you have a vault name from Vault Selection above, use project config or auto-detect:
```bash
cd <wiki-root> && python3 scripts/wiki_shared.py config 2>&1 | grep wiki_path
```
The wiki root is at the path declared in `.llm-wiki-config/config.json` under `wiki_path`, or auto-detected from Wiki/ + Schema/ directories.

## Workflow
1. **Identify the wiki root** for the selected vault (see Reference above).

2. **Detect repository type:**
   - Check for `.private-repo` marker file in wiki root (if present, treat as private)
   - Check `git remote -v` for known public hosting patterns (GitHub, GitLab)
   - Ask the user if repo type cannot be determined

3. **Choose audit mode based on repository type:**
   - **Public repo** (or user specifies `--mode public`): run full audit with path scan
   - **Private repo** (or user specifies `--mode private`): run secrets-only scan + wiki compliance checks

4. **Run fast security scan:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py security-scan --mode public|private
   ```

5. **Run full compliance audit:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py audit --mode public|private
   ```

6. **Report findings by severity:**
   - **Critical**: secrets, tokens, private keys — always blocks push (exit code 1)
   - **Warning**: broken wikilinks, orphaned notes, source coverage gaps — review recommended (exit code 2)
   - **Info**: local path patterns in public repos — normal in private repos

7. **Log results** if any findings were detected:
   ```bash
   cd <wiki-root> && python3 scripts/wiki_tool.py log --title "Audit results" --details "<summary>"
   ```

8. **Recommend next steps:**
   - For critical findings: fix the exposed secrets before pushing
   - For warnings: clean up broken references and orphaned notes at next opportunity

## Core Rules During Audit
- **Never report local paths as findings in private repos** — they are normal wiki content (file references, note links)
- **Critical findings always block** — secrets and tokens in tracked files must be fixed before pushing to public repos
- **Warnings never block** — orphaned notes and coverage gaps are quality issues, not security risks
- **Audit is separate from lint** — it checks security and exposure risk, not schema correctness. Lint handles frontmatter validation; audit handles secrets and compliance
- **Use configured patterns** — respect `.llm-wiki-config/audit-rules.json` if present; use built-in defaults otherwise
- **Respect skip lists** — do not scan files/directories listed in `skip_dirs` or `skip_files` rules
