---
name: llm-wiki-audit
description: Scan wiki repo for secrets, broken wikilinks, orphaned notes, and coverage gaps. Use before pushing to public repos or when user asks about security compliance.
compatibility: Python 3.8+, Git repo initialized, Chrome DevTools Protocol access
metadata:
  category: wiki-security
---

## When to use
Before pushing changes to a public repository, or when the user asks about security compliance.

## Prerequisites
- **Vault must be identified before any operation** — see Vault Selection below.


## Shared Infrastructure

**Pre-flight Check and Vault Selection are handled by the shared infrastructure.** See `references/shared-infra.md` for details.

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

## Error Handling

- **Vault selection fails** — If `obsidian list-vaults` returns no vaults, run llm-wiki-setup first
- **Obsidian CLI connection fails** — Verify Obsidian is running. Retry once after 10s, then report
- **Config missing** — If `.llm-wiki-config/config.json` is absent, run llm-wiki-setup before scanning
- **Git not initialized** — If `git status` fails, report that the repo is not a git repository and abort
- **Permission denied** — If scanning fails on specific files, skip them with a warning. Do not fail the entire audit

## What Not to Do (Anti-Patterns)

- **Do not report local paths in private repos** — Local file references are normal wiki behavior, not security findings
- **Do not skip critical findings** — Secrets and tokens found in tracked files MUST be reported. Never suppress them
- **Do not confuse audit with lint** — Audit checks security/exposure risk. Lint checks schema quality. Do not mix these concerns
- **Do not scan .git/ or node_modules/** — These directories are excluded by default. Do not add them to scan paths
- **Do not recommend deleting secrets** — Report exposed credentials but do NOT delete them. The user should rotate the credential first
