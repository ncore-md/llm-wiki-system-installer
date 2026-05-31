# LLM Wiki System

**A structured, agent-optimized knowledge base built on Obsidian.**

This directory is the shared wiki system — skills, tooling, and compiled notes. Each project that uses this system has its own `.llm-wiki-config/` folder at the project root, declaring which vaults are available and their permissions.

---

## Quick Overview

| Skill | Purpose | Triggered By |
|---|---|---|
| **ingest** | Create & update wiki notes from raw sources | User adds a URL, file, or pasted content |
| **query** | Answer questions from compiled knowledge | User asks something the wiki might know |
| **lint** | Validate frontmatter & schema before commits | Pre-commit gate, or user asks to check quality |
| **maintain** | Health checks: rebuild catalog, verify coverage | Periodic maintenance or before meaningful commits |
| **vl** | Analyze images → produce wiki notes | Automatically invoked by ingest for image sources |
| **setup** | Create `.llm-wiki-config/config.json` when missing | First-time run, no config found |

---

## Project Structure

```
/project-root/                          ← actual project folder (CWD)
├── .llm-wiki-config/                   ← PROJECT CONFIG (per project, not shared)
│   └── config.json                     ← vault declarations + permissions + defaults
│       {                              │  (this is the source of truth)
│         "wiki_path": "...",          │
│         "vaults": {...},             │
│         "defaults": {...}            │
│       }                              │
├── .llm-wiki/                          ← SHARED WIKI SYSTEM (read-only framework)
│   ├── Core/                           ← Wiki project directory (knowledge base)
│   │   ├── AGENTS.md                   ├─ wiki rules, allowed tags, directory map
│   │   ├── _templates/                 ├─ note templates per tag type
│   │   ├── Raw/                        ├─ raw source material (never compiled)
│   │   ├── Wiki/                       ├─ compiled knowledge (Topics, Concepts...)
│   │   ├── Schema/                     ├─ rules, schemas, cache
│   │   ├── scripts/                    ├─ wiki_tool.py + wiki_shared.py
│   │   └── .agents/skills/             └─ llm-wiki-* skill definitions (SKILL.md)
│   │       ├── llm-wiki-ingest/
│   │       ├── llm-wiki-query/
│   │       ├── llm-wiki-lint/
│   │       ├── llm-wiki-maintain/
│   │       ├── llm-wiki-vl/            ← vision language (image → notes)
│   │       └── llm-wiki-setup/         ← config setup (first-time only)
│
└── ... other project files ...
```

> **Key principle:** `.llm-wiki/` is the shared system (skills + tooling).
> `.llm-wiki-config/` is project-specific — each project declares its own vaults and permissions.

> Skills are defined in [`.agents/skills/`](.agents/skills/SKILLS.md). See that file for architecture, dependencies, and deployment model.

---

## The Seven Skills

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

**Key rules:**
- One concept per note, 3–5 key points max
- Every note must have `topics` with at least one wikilink to an existing topic
- Frontmatter arrays must use block-style YAML (`tags:\n  - concept`, NOT `tags: [concept]`)
- Never write one-off scripts — clean content in context using native tools

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

---

## Configuration System (`.llm-wiki-config/`)

### The Config File

Each project has a `.llm-wiki-config/config.json` at its root. This is the **single source of truth** for:

```json
{
  "wiki_path": "/absolute/path/to/.llm-wiki",

  "vaults": {
    "Core": {
      "wiki_root": "/path/to/.llm-wiki/Core",
      "permissions": ["read", "write", "ingest", "maintain"],
      "raw_paths": ["/path/to/.llm-wiki/Core/Raw/Sources"]
    },
    "NLite": {
      "wiki_root": "/path/to/NLite",
      "permissions": ["read"],
      "raw_paths": []
    }
  },

  "defaults": {
    "ingest_vault": "Core",
    "text_model_id": null,
    "vl_provider": "omlx",
    "vl_model_id": null,
    "vl_base_url": "http://localhost:8000/v1"
  }
}
```

| Field | Purpose | Required? |
|---|---|---|
| `wiki_path` | Path to the `.llm-wiki/` parent directory (or a specific wiki root) | Yes |
| `vaults.<name>.wiki_root` | Absolute path to the vault's wiki root (where AGENTS.md, _templates/, Wiki/, Schema/ live) | Yes |
| `vaults.<name>.permissions` | List of allowed operations: `read`, `write`, `ingest`, `maintain` | Yes |
| `vaults.<name>.raw_paths` | Explicit list of source directories for this vault. Flat paths — no auto-discovery from `Raw/` subdirs. Read-only vaults use empty array. | Yes (one per writable vault) |
| `defaults.ingest_vault` | Default target for ingest operations (must match a vault name) | No |
| `defaults.vl_provider` | Vision model provider (e.g., `omlx`, `openai`) | No |
| `defaults.vl_model_id` | Default model for image analysis (overrides cache defaults) | No |
| `defaults.vl_base_url` | Base URL for the VL model endpoint (e.g., `http://localhost:8000/v1`) | No |
| `defaults.text_model_id` | Default model for note generation (overrides cache defaults) | No |

### Permission Model

| Permission | What it allows |
|---|---|
| `read` | Read wiki notes, search catalog, query compiled knowledge |
| `write` | Create new notes, update existing ones (via obsidian_write) |
| `ingest` | Process raw sources, create notes from articles/images (full ingest pipeline) |
| `maintain` | Run build, lint, doctor commands on the wiki |

**A vault must have `read` permission for any operation.** Other permissions are additive — a vault with only `["write"]` can't be read from.

### Discovery Flow (How Skills Find Config)

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

The discovery is implemented in `wiki_shared.py`:
- **`find_project_config(wiki_root)`** — walks up from wiki root looking for `.llm-wiki-config/`
- **`load_project_config(wiki_root)`** — reads and validates `config.json`, returns dict or None
- **`get_project_config_path(wiki_root)`** — returns the config file path or None

---

## Pre-commit Hook

A git pre-commit hook lives at `.git/hooks/pre-commit`. It runs automatically before every commit and blocks if any check fails:

1. **`build`** — Rebuilds `catalog.jsonl`, `index.md`, and per-folder indexes
2. **`lint`** — Validates compiled note frontmatter (tags, dates, source paths, required sections)
3. **`source-lint`** — Validates raw source frontmatter and coverage state

This is the final safety gate. Step 6 of ingest (build + lint) provides immediate feedback during processing; the pre-commit hook catches anything missed.

## Per-Project, Not Shared

The `.llm-wiki/` directory is the **shared system** — skills, tooling, compiled notes. It does NOT contain per-project configuration.

Each project declares its own vaults and permissions in `.llm-wiki-config/config.json`. This means:
- The same wiki system can be used by multiple projects with different vault declarations
- Vault permissions are explicit, not assumed from directory names or Obsidian CLI output
- No hardcoded vaults — the config is the only source of truth

---

## Data Flow

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
    ┌──────────┐  ┌─────────┐   ┌──────────┐
    │ ingest   │  │ lint    │   │ query    │
    │ (write)  │  │(validate│   │ (read)   │
    └────┬─────┘  └────┬────┘   └────┬─────┘
         │             │             │
    Raw/Sources/   build→lint     catalog search
         │           check        read compiled notes
    Wiki/{Topics,  source-lint   synthesize answer
          Concepts,...}│           │
         │            commit       ▼
    git commit ◄───────┘   Raw sources (if needed)
         │
    ┌────┴─────┐
    │ vl       │ ← Spawned by ingest for images
    │ (subagent)│   Produces markdown notes via ---NOTE_BOUNDARY---
    └──────────┘

> **Vault selection detail:** Vault names are validated against declared config. Wrong names stop the operation — the user is shown available vaults and asked to correct. The `all` keyword expands to every declared vault, each processed independently (no shared state between vaults). See the ingest skill for full validation rules.

First run (no config):
                    ┌──────────────┐
                    │ User Request  │
                    └───────┬──────┘
                            ▼
              ┌─────────────────────────┐
              │  No config found?       │ ← find_project_config() returns None
              └────────┬────────────────┘
                       │
                       ▼
              ┌─────────────────────────┐
              │  Run setup skill        │ ← llm-wiki-setup/SKILL.md
              │  obsidian vaults →      │ ← List available Obsidian vaults
              │  user selects + assigns │ ← Role per vault (primary/read-only)
              │  write config.json      │ ← Create .llm-wiki-config/
              └────────┬────────────────┘
                       │
                       ▼
              ┌─────────────────────────┐
              │  Config exists now      │ ← Re-run original skill
              └────────┬────────────────┘
                       ▼
              Proceed with declared vaults
```

---

## Core Rules (Non-Negotiable)

1. **Keep Raw sources faithful.** Never overwrite original content during compilation.
2. **One concept per note, 3–5 key points max.** Split or truncate if more.
3. **Plain tags only** — no formatting in frontmatter, never inline `#tags`.
4. **Always include topics and sources** on every compiled note — even if empty (`[]`).
5. **Query from catalog first**, not raw Obsidian search or broad context scans.
6. **Set source_count at write time, verify via build.** It must match the number of entries in `sources` when creating/updating notes, then run `build` to recalculate and validate. Never commit with a mismatched count.
7. **Never overwrite Raw sources** when creating or updating Wiki notes.

---

## Tag Routing

Tag routing is **discovered per-vault** from each vault's `AGENTS.md` Directory Structure table. The script (`wiki_shared.py`) parses Wiki/ folder entries from that table and maps them to tags. If no table exists, it falls back to scanning actual Wiki/ subdirectories.

This means different vaults can have completely different folder structures for the same tags. The table below shows the **common convention** — what most vaults' AGENTS.md declares:

| Tag | Convention Folder | What goes here |
|---|---|---|
| `topic` | Wiki/Topics/ | Broad subject areas (e.g., "LLM Wiki", "RAG") |
| `concept` | Wiki/Concepts/ | Discrete ideas, definitions, mechanisms (e.g., "Shared Memory Layer") |
| `entity` | Wiki/Entities/ | People, organizations, tools (e.g., "Anthropic", "Claude") |
| `project` | Wiki/Projects/ | Initiatives with scope & status (e.g., "Wiki Migration") |
| `log` | Wiki/Logs/ | Activity logs, changelogs, operational records |

To discover the actual routing for a vault: `python3 scripts/wiki_shared.py config --force` → check `tag_routing` in the output.

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

## File I/O Discipline

| Operation | Method | Why |
|---|---|---|
| Read wiki notes | `obsidian` CLI or native `obsidian_read` | Safe, handles YAML properly |
| Create/overwrite notes | Native `obsidian_write` tool | Structured params, no shell escaping issues |
| Append to notes | Native `obsidian_append` tool | Clean append without full replacement |
| Set note properties | `obsidian property:set` | For single-value fields only (not list append) |
| Run wiki tooling | `python3 scripts/wiki_tool.py ...` | Enforces schema rules Obsidian doesn't know |
| Git operations | `git add && git commit` | Outside Obsidian scope; pre-commit hook runs safety checks |
| Write config files | `write` tool (non-vault files) | Config is outside Obsidian scope — safe to use raw filesystem |

**Never use raw filesystem `write` on vault files.** This risks YAML corruption, broken wikilinks, and encoding issues.

---

## Getting Started (First Run)

```bash
# 1. If no config exists, the setup skill will trigger automatically
#    Or run manually: /llm-wiki-setup

# 2. After setup, check what's configured
python3 scripts/wiki_shared.py config --force

# 3. Run health check on a wiki
python3 scripts/wiki_tool.py doctor

# 4. Scan for new raw sources to process
python3 scripts/wiki_tool.py source-scan --update
# 5. After ingesting, update manifest with coverage validation
python3 scripts/wiki_tool.py source-scan --update --accept-covered

# 5. Build catalog and validate
python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint

# 6. Search the catalog
python3 scripts/wiki_tool.py search-catalog --query "your topic"

# 7. Discover available VL models (for image processing)
python3 scripts/wiki_shared.py discover

# 8. Set a default model for note generation
python3 scripts/wiki_shared.py set-default text_model_id "your-model-id"
```

## Getting Started (Existing Config)

```bash
# Check declared vaults and permissions
python3 scripts/wiki_shared.py vaults

# Discover wiki structure + validate config
python3 scripts/wiki_shared.py config --force

# Run health check
python3 scripts/wiki_tool.py doctor && python3 scripts/wiki_tool.py lint

# Ingest a new source (will use defaults.ingest_vault)
/llm-wiki-ingest "https://example.com/article"

# Query the wiki (will use defaults.ingest_vault)
/llm-wiki-query "What is RAG?"

# Lint before commit (will use defaults.ingest_vault)
/llm-wiki-lint

# Maintain all declared vaults
/llm-wiki-maintain
```
