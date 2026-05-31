# LLM Wiki System

**A structured, agent-optimized knowledge base built on Obsidian.**

Turns raw source material into organized, queryable knowledge that AI agents and humans can use. Ingest articles, notes, and transcripts → compile into structured Wiki notes → validate on every commit → query via a searchable catalog.

---

## Table of Contents

1. [Quick Start](#quick-start)
2. [What Gets Installed](#what-gets-installed)
3. [First Run Setup](#first-run-setup)
4. [Daily Workflow](#daily-workflow)
5. [Security & Compliance](#security--compliance) ⭐ **NEW**
6. [Architecture Overview](#architecture-overview)
7. [Command Reference](#command-reference) ⭐ **NEW**
8. [The Seven Skills](#the-seven-skills)
9. [Troubleshooting](#troubleshooting) ⭐ **NEW**
10. [FAQ & Notes](#faq--notes)

---

## 1. What is LLM Wiki?

LLM Wiki turns raw source material into organized, queryable knowledge that AI agents and humans can use. It manages a pipeline from raw sources (articles, notes, transcripts) through compilation into structured Wiki notes with strict quality gates — every commit runs build + lint checks, and pushes to public repos are scanned for secrets before they leave your machine.

Think of it as a **knowledge base framework** that lives alongside Obsidian: the `.llm-wiki/` directory holds skills, tooling, and compiled notes as a shared system; each project declares its own vaults and permissions in `.llm-wiki-config/config.json`.

---

## 2. Quick Start

### Installation

#### Quick install (one-liner)

```bash
git clone https://github.com/ncore-md/llm-wiki-system-installer.git && cd llm-wiki-system-installer && bash scripts/setup-wizard.sh
```

#### Step-by-step

**Step 1:** Clone the installer into your project root:

```bash
git clone https://github.com/ncore-md/llm-wiki-system-installer.git
```

**Step 2:** Run the setup wizard:

```bash
cd llm-wiki-system-installer && bash scripts/setup-wizard.sh
```

The wizard creates your vault structure, copies skills and tooling into the vault, installs git hooks (pre-commit + pre-push), registers the vault path, and validates with an initial build.

### One-Liner for Humans & Agents

| Mode | Command / Env Vars |
|------|-------------------|
| **Human (interactive)** | `bash llm-wiki-system-installer/scripts/setup-wizard.sh` → choose mode, select vault |
| **Agent (non-interactive)** | `export SETUP_MODE=1 && export SETUP_VAULT_NAME="MyWiki" && bash llm-wiki-system-installer/scripts/setup-wizard.sh` |

---

## 3. What Gets Installed

```
<project-root>/                          ← your project folder (CWD)
├── .llm-wiki-config/                    ← PROJECT CONFIG (per project, not shared)
│   └── config.json                      ← vault declarations + permissions + defaults
├── .llm-wiki/                           ← SHARED WIKI SYSTEM (read-only framework)
│   ├── Core/                            ← Wiki project directory (knowledge base)
│   │   ├── AGENTS.md                    ← wiki rules, allowed tags, directory map
│   │   ├── Welcome.md                   ← vault welcome note
│   │   ├── _templates/                  ← 7 note templates (concept, entity, topic…)
│   │   ├── Raw/                         ← raw source material (never compiled)
│   │   │   └── Sources/                 ← add cleaned markdown here
│   │   ├── Wiki/                        ← compiled knowledge (queryable, linked)
│   │   │   ├── Topics/, Concepts/       ← compiled notes by type
│   │   │   ├── Entities/, Projects/     ← people, orgs, initiatives
│   │   │   └── Logs/                    ← activity logs, changelogs
│   │   ├── Schema/                      ← rules, schemas, cache definitions
│   │   ├── scripts/                     ← wiki_tool.py + wiki_shared.py
│   │   └── .agents/skills/              ← 7 skill definitions (SKILL.md)
│   │       ├── llm-wiki-ingest/         ← create & update notes from sources
│   │       ├── llm-wiki-query/          ← answer questions from compiled knowledge
│   │       ├── llm-wiki-lint/           ← validate frontmatter & schema before commits
│   │       ├── llm-wiki-maintain/       ← health checks, rebuild catalog
│   │       ├── llm-wiki-vl/             ← vision language (image → notes)
│   │       ├── llm-wiki-setup/          ← create config.json (first-time only)
│   │       └── llm-wiki-audit/          ← compliance & security auditing
│   │
├── .git/hooks/pre-commit                ← build + lint on every commit (auto)
├── .git/hooks/pre-push                  ← security scan before pushing to public repos (auto)
├── .gitignore                           ← excludes cache, node_modules, etc.
│
└── llm-wiki-system-installer/           ← installer package (can be removed after setup)
    ├── scripts/setup-wizard.sh          ← the wizard itself
    ├── hooks/pre-commit                 ← pre-commit hook template
    ├── hooks/pre-push                   ← pre-push security gate template
    └── .llm-wiki-config/audit-rules.json ← configurable security rules
```

> **Key principle:** `.llm-wiki/` is the shared system (skills + tooling).
> `.llm-wiki-config/` is project-specific — each project declares its own vaults and permissions.

---

## 4. First Run Setup

### Step 1: Run the Wizard

```bash
# Interactive — choose mode and select vault
bash llm-wiki-system-installer/scripts/setup-wizard.sh

# Non-interactive (agents)
export SETUP_MODE=1           # 1 = create new, 2 = apply to existing
export SETUP_VAULT_NAME="Core"
export SETUP_CONFIRM=y        # skip confirmation prompt
bash llm-wiki-system-installer/scripts/setup-wizard.sh

# Optional overrides
export SETUP_VAULT_PATH="/path/to/custom/vault"
```

### Step 2: Config Creation (Per-Project)

After the wizard creates your vault structure, `.llm-wiki-config/config.json` is created by the `llm-wiki-setup` skill — **not** by the installer. This is a per-project file, not shared:

```json
{
  "wiki_path": "/absolute/path/to/.llm-wiki",

  "vaults": {
    "Core": {
      "wiki_root": "/path/to/.llm-wiki/Core",
      "permissions": ["read", "write", "ingest", "maintain"],
      "raw_paths": ["/path/to/.llm-wiki/Core/Raw/Sources"]
    }
  },

  "defaults": {
    "ingest_vault": "Core",
    "text_model_id": null,
    "vl_provider": "omlx"
  }
}
```

| Field | Purpose | Required? |
|-------|---------|-----------|
| `wiki_path` | Path to the `.llm-wiki/` parent directory or a specific wiki root | Yes |
| `vaults.<name>.wiki_root` | Absolute path to the vault's wiki root (where AGENTS.md, Wiki/, Schema/ live) | Yes |
| `vaults.<name>.permissions` | Allowed operations: `read`, `write`, `ingest`, `maintain` | Yes |
| `vaults.<name>.raw_paths` | Source directories for this vault. Empty array = read-only. | Yes (one per writable vault) |
| `defaults.ingest_vault` | Default target for ingest operations (must match a vault name) | No |
| `defaults.vl_provider` | Vision model provider (`omlx`, `openai`) | No |
| `defaults.vl_model_id` | Default model for image analysis | No |

### Step 3: Validate Setup

```bash
# Check declared vaults and permissions
python3 scripts/wiki_shared.py config --force

# Run health check on a wiki
python3 scripts/wiki_tool.py doctor

# Discover available VL models (for image processing)
python3 scripts/wiki_shared.py discover
```

---

## 5. Daily Workflow

The standard knowledge management loop: **ingest → compile → query → lint**

```
1. Ingest a source
   /llm-wiki-ingest "https://example.com/article"

2. Query the wiki before creating new notes
   /llm-wiki-query "What is RAG?"

3. Lint before committing
   /llm-wiki-lint

4. Periodic maintenance (weekly or before meaningful commits)
   /llm-wiki-maintain
```

### Manual CLI Workflow (without slash commands)

```bash
# Scan for new raw sources to process
python3 scripts/wiki_tool.py source-scan --update

# Ingest a new source (will use defaults.ingest_vault)
/llm-wiki-ingest "https://example.com/article"

# After ingesting, update manifest with coverage validation
python3 scripts/wiki_tool.py source-scan --update --accept-covered

# Build catalog and validate
python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint

# Search the catalog
python3 scripts/wiki_tool.py search-catalog --query "your topic"

# Query the wiki
/llm-wiki-query "What is RAG?"

# Lint before commit
/llm-wiki-lint

# Maintain all declared vaults
/llm-wiki-maintain
```

---

## 6. Security & Compliance ⭐ **NEW**

LLM Wiki includes a built-in security gate that runs automatically before you push code to remote repositories. This is critical for wikis that may reference external sources, contain API keys in notes, or inadvertently expose sensitive information.

### Pre-Push Security Scan

When you run `git push` to a public repository, the pre-push hook automatically:

1. **Checks for `.private-repo` marker** — if the file exists, all scans are skipped (for private repos)
2. **Runs `security-scan --mode public`** — scans for secrets (API keys, tokens, passwords)
3. **Runs `audit --mode public`** — full compliance audit (broken links, orphaned notes, source coverage)

```bash
# Manual pre-push checks:
python3 scripts/wiki_tool.py security-scan --mode public
python3 wiki_tool.py audit --mode public

# Mark a repo as private (skips security scan):
touch .private-repo
```

### What the Scanner Detects

| Category | Examples | Severity |
|----------|---------|----------|
| **Private keys** | `-----BEGIN RSA PRIVATE KEY-----` | Critical |
| **API tokens** | OpenAI keys (`sk-proj-...`), GitHub PATs (`ghp_...`, `github_pat_...`) | Critical |
| **Cloud credentials** | AWS access keys (`AKIA...`), Bearer tokens, Slack tokens | Critical |
| **Passwords** | `password = "..."` in configs or comments | Critical |
| **Local paths** | `/Users/...`, `C:\AppData\...` in tracked files | Warning |
| **Wiki health** | Broken wikilinks, orphaned notes, source coverage gaps | Warning/Error |

### Configurable Rules

Security rules live in `.llm-wiki-config/audit-rules.json` (copied from the installer's bundled config):

```json
{
  "secrets_patterns": [ ... ],       // Regex patterns for secrets detection
  "skip_dirs": [".git", ".obsidian/cache"], // Directories to skip during scan
  "skip_files": ["wiki_tool.py", "wiki_shared.py"], // Files to skip (tooling)
  "path_scan": {                      // Local path detection config
    "enabled_in_public": true,
    "patterns": ["^/Users/", "^/home/", "[A-Z]:\\\\"]
  },
  "wiki_checks": {                    // Wiki health checks enabled in audit
    "broken_wikilinks": true,
    "orphaned_notes": true,
    "source_coverage_gaps": true
  }
}
```

### Git Hooks (Auto-Installed)

| Hook | Runs On | Commands Executed |
|------|---------|------------------|
| **pre-commit** | Every `git commit` | `build`, `lint`, `source-lint` — validates catalog, frontmatter, and source coverage |
| **pre-push** | Every `git push` to public repos | `security-scan --mode public`, `audit --mode public` — checks for secrets and compliance |

Both hooks are installed automatically by the setup wizard. They **block** on failure — you must fix issues before committing or pushing.

---

## 7. Command Reference ⭐ **NEW**

### wiki_tool.py Commands

| Command | Description | Example |
|---------|-------------|---------|
| `build` | Rebuilds catalog, indexes, and per-folder indexes | `python3 scripts/wiki_tool.py build` |
| `lint` | Validates compiled note frontmatter (tags, dates, sources) | `python3 scripts/wiki_tool.py lint` |
| `source-lint` | Validates raw source frontmatter and coverage state | `python3 scripts/wiki_tool.py source-lint` |
| `search-catalog --query "..."` | Search compiled knowledge via catalog (not raw Obsidian search) | `python3 scripts/wiki_tool.py search-catalog --query "RAG"` |
| `doctor` | Health check on the wiki system | `python3 scripts/wiki_tool.py doctor` |
| `security-scan --mode public\|private` | Scan for secrets and local paths in tracked files | `python3 scripts/wiki_tool.py security-scan --mode public` |
| `audit --mode public\|private` | Full compliance audit: security + wiki health checks | `python3 scripts/wiki_tool.py audit --mode public` |
| `source-scan --update [--accept-covered]` | Scan Raw/Sources/ for new or updated files, update manifest | `python3 scripts/wiki_tool.py source-scan --update` |

### wiki_shared.py Commands

| Command | Description | Example |
|---------|-------------|---------|
| `config --force` | Validate config, show vaults and tag routing | `python3 scripts/wiki_shared.py config --force` |
| `vaults` | List declared vaults and permissions | `python3 scripts/wiki_shared.py vaults` |
| `discover` | Discover available VL models for image processing | `python3 scripts/wiki_shared.py discover` |
| `set-default <field> <value>` | Set a default config value (e.g., text_model_id) | `python3 scripts/wiki_shared.py set-default text_model_id "gpt-4o"` |

### Slash Commands (Skill Triggers)

| Command | Skill | Description |
|---------|-------|-------------|
| `/llm-wiki-ingest "..."` | llm-wiki-ingest | Create & update wiki notes from raw sources (URL, file, pasted content) |
| `/llm-wiki-query "..."` | llm-wiki-query | Answer questions from compiled knowledge via catalog search |
| `/llm-wiki-lint` | llm-wiki-lint | Validate frontmatter and schema before commits |
| `/llm-wiki-maintain` | llm-wiki-maintain | Health checks: rebuild catalog, verify coverage, report issues |
| `/llm-wiki-setup` | llm-wiki-setup | Create `.llm-wiki-config/config.json` when missing (first-time only) |

---

## 8. Architecture Overview

### Directory Layout: Shared System vs Project Config

```
/project-root/                          ← actual project folder (CWD)
├── .llm-wiki-config/                   ← PROJECT CONFIG (per project, not shared)
│   └── config.json                     ← vault declarations + permissions + defaults
├── .llm-wiki/                          ← SHARED WIKI SYSTEM (read-only framework)
│   ├── Core/                           ← Wiki project directory (knowledge base)
│   │   ├── AGENTS.md                   ├─ wiki rules, allowed tags, directory map
│   │   ├── _templates/                 ├─ note templates per tag type
│   │   ├── Raw/                        ├─ raw source material (never compiled)
│   │   │   └── Sources/                ├─ add cleaned markdown here
│   │   ├── Wiki/                       ├─ compiled knowledge (Topics, Concepts...)
│   │   ├── Schema/                     ├─ rules, schemas, cache definitions
│   │   ├── scripts/                    ├─ wiki_tool.py + wiki_shared.py
│   │   └── .agents/skills/             └─ 7 skill definitions (SKILL.md)
│   │       ├── llm-wiki-ingest/        ← create & update notes from sources
│   │       ├── llm-wiki-query/         ← answer questions from compiled knowledge
│   │       ├── llm-wiki-lint/          ← validate frontmatter & schema before commits
│   │       ├── llm-wiki-maintain/      ← health checks, rebuild catalog
│   │       ├── llm-wiki-vl/            ← vision language (image → notes)
│   │       ├── llm-wiki-setup/         ← config setup (first-time only)
│   │       └── llm-wiki-audit/         ← compliance & security auditing
│   │
├── .git/hooks/pre-commit               ← build + lint on every commit (auto)
└── .git/hooks/pre-push                 ← security scan before pushing (auto)

> **Key principle:** `.llm-wiki/` is the shared system.
> `.llm-wiki-config/` is project-specific — each project declares its own vaults and permissions.
```

### Data Flow Diagram

```
                    ┌──────────────┐
                    │ User Request  │
                    └───────┬──────┘
                            ▼
              ┌─────────────────────────┐
              │  Vault Selection        │ ← Check args, or list from config
              └────────┬────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
    ┌──────────┐  ┌─────────┐   ┌──────────────┐
    │ ingest   │  │ lint    │   │ query        │
    │ (write)  │  │(validate│   │ (read)       │
    └────┬─────┘  └────┬────┘   └──────┬───────┘
         │             │               │
    Raw/Sources/   build→lint     catalog search
         │           check        read compiled notes
    Wiki/{Topics,  source-lint   synthesize answer
          Concepts,...}│           │
         │            commit       ▼
    git commit ◄───────┘   Raw sources (if needed)
         │
    ┌────┴─────┐
    │ pre-push │ ← security-scan + audit (public repos only)
    └──────────┘

First run (no config):
                    ┌──────────────┐
                    │ User Request  │
                    └───────┬──────┘
                            ▼
              ┌─────────────────────────┐
              │  No config found?       │ ← find_project_config() returns None
              └────────┬────────────────┘
                       ▼
              ┌─────────────────────────┐
              │  Run llm-wiki-setup     │ ← Create .llm-wiki-config/config.json
              │  obsidian vaults →      │ ← List available Obsidian vaults
              │  user selects + assigns │ ← Role per vault (primary/read-only)
              └────────┬────────────────┘
                       ▼
              Proceed with declared vaults
```

### Config Discovery Flow

```
Skill invoked → find wiki root (Wiki/ + Schema/) → walk up for .llm-wiki-config/config.json
                                                          │
                                                  ┌───────┴───────┐
                                                  │               │
                                            Found?            Missing?
                                              │                 │
                                               ▼                ▼
                                        Read config →       Run setup skill:
                                        validate vaults     1. obsidian vaults --verbose
                                        proceed with       2. User selects + assigns roles
                                        declared vaults    3. Write config.json
                                                          4. Validate → done
```

### Tag Routing (Per-Vault)

Tag routing is **discovered per-vault** from each vault's `AGENTS.md` Directory Structure table. Different vaults can have completely different folder structures for the same tags.

| Tag | Convention Folder | What goes here |
|-----|-------------------|---------------|
| `topic` | Wiki/Topics/ | Broad subject areas (e.g., "LLM Wiki", "RAG") |
| `concept` | Wiki/Concepts/ | Discrete ideas, definitions, mechanisms (e.g., "Shared Memory Layer") |
| `entity` | Wiki/Entities/ | People, organizations, tools (e.g., "Anthropic", "Claude") |
| `project` | Wiki/Projects/ | Initiatives with scope & status (e.g., "Wiki Migration") |
| `log` | Wiki/Logs/ | Activity logs, changelogs, operational records |

Discover actual routing for a vault: `python3 scripts/wiki_shared.py config --force` → check `tag_routing` in output.

---

## 9. The Seven Skills

### 1. `llm-wiki-ingest` — Create & Update Notes

**The orchestrator.** Handles the full pipeline from raw source to committed wiki note.

```
Step 0: Check for pending sources (markdown + images) in Raw/Sources/
   │
   ├── Image found? → Discover VL model → Spawn llm-wiki-vl subagent
   │                    └── Parse output (---NOTE_BOUNDARY---) → Write notes
   │
   ├── Markdown found? → Clean & store in Raw/Sources/
   │                      → Search catalog for related topics
   │                      → Read existing wiki notes on those topics
   │                      → Create or update compiled wiki note
   │
Step 6: build + lint (quality gate)
Step 7: Update source manifest
Step 8: Log the change
Step 9: Git commit (pre-commit hook runs safety checks)
```

**Key rules:** One concept per note, 3–5 key points max. Every note must have `topics` with at least one wikilink to an existing topic. Block-style YAML only (`tags:\n  - concept`, NOT `tags: [concept]`).

### 2. `llm-wiki-query` — Answer from Compiled Knowledge

**The read path.** Answers user questions by searching and synthesizing from compiled wiki notes.

```
1. Search Wiki/index.md for overview
2. Query catalog (not raw Obsidian search) via wiki_tool.py search-catalog
3. Read the most relevant compiled notes (top matches only)
4. Synthesize answer from distilled knowledge
5. Fall back to Raw sources only if compiled notes are insufficient
```

**Core rule:** Always prefer compiled Wiki notes over raw source material — they're pre-distilled and structured.

### 3. `llm-wiki-lint` — Validate Before Commit

**The pre-commit gate.** Lightweight validation of frontmatter and schema.

```
1. Identify wiki root for the selected vault
2. Read AGENTS.md → get allowed tags & required fields
3. Check frontmatter: tags array, topics/sources present, date formats
4. Verify source_count matches sources array length
5. Run wiki_tool.py lint + wiki_tool.py source-lint
6. Report issues — never commit past a failed lint
```

### 4. `llm-wiki-maintain` — Periodic Health Checks

**The maintenance routine.** Broader than lint: rebuilds, verifies coverage, reports.

```
1. wiki_tool.py doctor          → Health check
2. wiki_tool.py build           → Rebuild catalog + indexes
3. wiki_tool.py lint            → Validate compiled notes
4. wiki_tool.py source-lint     → Check Raw source coverage
5. Log changes + report results
```

### 5. `llm-wiki-vl` — Vision Language (Image → Notes)

**Subagent-only.** Never triggered directly by the user. Injected into a vision-capable subagent when ingest encounters an image source.

```
1. Read the image natively (via read tool, no base64)
2. Extract text, labels, structure, visual elements
3. Identify wiki-worthy concepts → produce clean markdown notes
4. Output format: YAML frontmatter + body, separated by ---NOTE_BOUNDARY---
```

**Strict output rules:** No preamble, no reasoning text, block-style frontmatter only, topics ≥1 wikilink, real filenames from provided list.

### 6. `llm-wiki-setup` — Create Project Config

**First-time only.** When `.llm-wiki-config/config.json` is missing, this skill guides the user through setting up vault declarations.

```
1. Check for existing config → if found, done
2. Use obsidian CLI to list available vaults
3. User selects vaults and assigns roles (primary / read-only)
4. Set defaults: ingest_vault, text_model_id, vl_model_id
5. Write .llm-wiki-config/config.json
6. Validate and cache → report success
```

### 7. `llm-wiki-audit` — Compliance & Security Auditing

**The compliance checker.** Runs security scans and wiki health audits. Used by the pre-push hook automatically, or manually via CLI.

```
1. security-scan --mode public|private  → Detect secrets in tracked files
2. audit --mode public                  → Full compliance: security + wiki health
3. Report findings with severity levels  → Critical / Warning / Error
```

---

## 10. Troubleshooting ⭐ **NEW**

### Common Issues

| Problem | Cause | Fix |
|---------|-------|-----|
| **"No config found"** | `.llm-wiki-config/config.json` doesn't exist yet | Run `/llm-wiki-setup` or `bash setup-wizard.sh` with env vars |
| **"Obsidian CLI not found"** | `obsidian` command not in PATH or app not running | Install Obsidian CLI, ensure Obsidian is launched before setup |
| **"Obsidian not running"** | CLI found but app isn't responding | Launch Obsidian, then re-run `obsidian version` to confirm |
| **Pre-commit hook fails** | Build or lint errors in recent changes | Fix frontmatter issues (tags format, source_count mismatch), then retry commit |
| **Pre-push hook blocks** | Secrets detected in tracked files | Remove sensitive data from notes, add to `.gitignore` or use `.private-repo` marker |
| **Broken wikilinks after refactor** | Moved/renamed notes without updating references | Run `wiki_tool.py lint` to find broken links, update with wikilink tooling |
| **Orphaned notes detected** | Notes not linked from index or other notes | Review with `wiki_tool.py audit`, either link them or remove if stale |
| **source_count mismatch** | `sources` array length doesn't match declared count | Run `wiki_tool.py build` to recalculate, or manually fix the count in frontmatter |
| **Tags not routing correctly** | AGENTS.md tag table differs from expected convention | Run `wiki_shared.py config --force` to check actual routing for your vault |

### Pre-Flight Checklist (Before First Use)

```bash
# 1. Verify prerequisites
command -v obsidian && echo "Obsidian CLI: OK" || warn "Missing Obsidian CLI"
command -v python3 && echo "Python: OK" || warn "Missing Python 3"

# 2. Verify config exists
test -f .llm-wiki-config/config.json && echo "Config: OK" || run_setup

# 3. Verify hooks are installed
test -x .git/hooks/pre-commit && echo "Pre-commit hook: OK" || warn "Hook missing"
test -x .git/hooks/pre-push && echo "Pre-push hook: OK" || warn "Hook missing"

# 4. Run initial validation
python3 scripts/wiki_tool.py doctor && python3 scripts/wiki_tool.py lint
```

---

## 11. FAQ & Notes

### Is `.llm-wiki-config/` shared across projects?
**No.** It's per-project. Each project declares its own vaults and permissions in `.llm-wiki-config/config.json`. The shared system lives only in `.llm-wiki/`.

### Can I use this with multiple vaults?
Yes. Declare all vaults in `config.json` under the `vaults` key, with appropriate permissions. The `all` keyword expands to every declared vault during maintenance operations — each processed independently with no shared state.

### Can I remove the installer after setup?
Yes. Once `setup-wizard.sh` has copied all files into your vault, the installer folder is no longer needed. Keep it only if you want to run setup on additional vaults later.

### How do I mark a repo as private?
Create an empty `.private-repo` file in the project root. The pre-push hook will skip all security scans for that repository.

### What if my vault has a different folder structure?
Tag routing is discovered from each vault's `AGENTS.md` Directory Structure table. If no table exists, it falls back to scanning actual Wiki/ subdirectories. Different vaults can have completely different structures for the same tags.

### What's the difference between lint and maintain?
`lint` is lightweight — validates frontmatter schema before commits. `maintain` is broader: rebuilds the catalog, verifies source coverage, runs health checks, and reports. Use lint on every commit; use maintain periodically or before meaningful commits.

### Is there a Portuguese version?
Yes — see `README.pt-BR.md` in the installer folder.

---

## Core Rules (Non-Negotiable)

1. **Keep Raw sources faithful.** Never overwrite original content during compilation.
2. **One concept per note, 3–5 key points max.** Split or truncate if more.
3. **Plain tags only** — no formatting in frontmatter, never inline `#tags`.
4. **Always include topics and sources** on every compiled note — even if empty (`[]`).
5. **Query from catalog first**, not raw Obsidian search or broad context scans.
6. **Set source_count at write time, verify via build.** Never commit with a mismatched count.
7. **Never overwrite Raw sources** when creating or updating Wiki notes.

---

## File I/O Discipline

| Operation | Method | Why |
|-----------|--------|-----|
| Read wiki notes | `obsidian` CLI or native `obsidian_read` | Safe, handles YAML properly |
| Create/overwrite notes | Native `obsidian_write` tool | Structured params, no shell escaping issues |
| Append to notes | Native `obsidian_append` tool | Clean append without full replacement |
| Set note properties | `obsidian property:set` | For single-value fields only (not list append) |
| Run wiki tooling | `python3 scripts/wiki_tool.py ...` | Enforces schema rules Obsidian doesn't know |
| Git operations | `git add && git commit` | Outside Obsidian scope; pre-commit hook runs safety checks |
| Write config files | `write` tool (non-vault files) | Config is outside Obsidian scope — safe to use raw filesystem |

**Never use raw filesystem `write` on vault files.** This risks YAML corruption, broken wikilinks, and encoding issues.

---

## Frontmatter Contract (Block-Style Required)

```yaml
tags:
  - concept              # Must be block array, NOT scalar or inline
topics:
  - [[Existing Topic]]   # At least one wikilink — never empty
status: draft            # Or "published"
created: 2026-05-29      # YYYY-MM-DD format
updated: 2026-05-29      # YYYY-MM-DD format
sources:
  - "[[Raw/Sources/file.md]]"  # Wikilinks, NOT empty [] or body text
source_count: 1          # Must match sources array length
```

**Common pitfalls:**
- `sources: []` in YAML but content under `## Sources:` — the body section does NOT populate frontmatter
- Escaped quotes (`\"`) in YAML that don't match on-disk filenames — causes lint failures
- Scalar `tags: concept` instead of block array `tags:\n  - concept` — breaks parser

---

*LLM Wiki System — structured, agent-optimized knowledge base built on Obsidian.*
