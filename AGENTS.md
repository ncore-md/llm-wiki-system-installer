# Agent Rules — LLM Wiki
---checklist---
max_topics: 5
required_sections:
  - "## Related"
  - "## Sources"
allowed_tags: [topic, concept, entity, project]
topics_required_for:
  - concept
  - entity
tag_routing:
  Topics: topic
  Concepts: concept
  Entities: entity
  Projects: project
source_tag: [source]
allowed_content_types:
  - video
  - article
  - markdown
  - pdf
source_count_required: true
---
> **Optimized for Pi.** This vault is built to be agent-agnostic, but all workflows and tooling are optimized for Pi. See [[Pi (Coding Agent)]] for details.

## Related System Files

### Schema (rules & references)
- [[Schema/frontmatter-schema.md]] — Frontmatter rules and validation definitions
- [[Schema/naming-conventions.md]] — Naming conventions for notes, tags, and paths
- [[Schema/lint-checklist.md]] — Pre-commit lint checklist
- [[Schema/command-reference.md]] — CLI command reference (wiki_tool.py)

### Templates (_templates/)
- [_templates/concept-note.md] — Template for concept notes
- [_templates/entity-note.md] — Template for entity notes
- [_templates/topic-note.md] — Template for topic notes
- [_templates/project-note.md] — Template for project notes
- [_templates/log-note.md] — Template for log entries
- [_templates/source-note.md] — Template for raw source notes
- [_templates/session-log.md] — Template for session logs

### Tooling & Skills
- [[scripts/wiki_tool.py]] — Validation tools: build, lint, search-catalog, audit
- `.agents/skills/` — Agent skills (ingest, query, lint, maintain, audit)
- `.llm-wiki-config/audit-rules.json` — Configurable security scan patterns (optional, uses defaults if missing)
- [[Welcome.md]] — Getting started guide

## Directory Structure

| Path | Role |
|------|------|
| `Raw/Sources/` | **Source material only.** Original notes, articles, transcripts. Never compile knowledge here — this is the source of truth for unprocessed content. |
| `Raw/Files/` | Binary attachments (images, PDFs) referenced by sources. |
| `Wiki/Topics/` | Compiled topic notes — broad subject areas covered by the Wiki. |
| `Wiki/Concepts/` | Compiled concept notes — discrete ideas, definitions, mechanisms. |
| `Wiki/Entities/` | Compiled entity notes — people, organizations, tools, places. |
| `Wiki/Projects/` | Compiled project notes — initiatives with scope and status. |
| `Wiki/Logs/` | Activity logs, change records — one note per meaningful action. |
| `Schema/` | Rules, schemas, catalog manifest files. Not user-facing notes. |
| `_templates/` | Note templates for new content creation — do not edit without reason. |
| `scripts/` | Tooling scripts (wiki_tool.py, wiki_shared.py). Do not edit without reason. |
| `.agents/skills/` | Agent skill definitions (ingest, query, lint, maintain). |
| `tutorial/` | Tutorial files and documentation. Empty until populated. |

## Core Rules (Non-Negotiable)

1. **Keep Raw source notes source-faithful.** Do not overwrite Raw content during compilation (keep the original).
2. **Keep compiled Wiki notes short and single-purpose.** One concept per note, one topic cluster. A single raw source may contain multiple distinct concepts — create separate notes for each.
3. **Use plain tags only** (no formatting). Always use #tags in frontmatter, never inline.
4. **Always keep topics and sources on every compiled Wiki note.** Even if empty (topics: [], sources: []).
5. **Always query from `Wiki/index.md` and `Wiki/catalog.jsonl`** before opening broad context.
6. **Treat source_count as derived, not manually set.** Always run build after updates.
7. **Never overwrite Raw sources** when creating or updating Wiki notes.

## Allowed Tags for Compiled Wiki Notes

- `topic` — broad subject areas
- `concept` — discrete ideas, definitions, mechanisms
- `entity` — people, organizations, tools, places
- `project` — initiatives with scope and status
- `log` — activity logs, change records

## Ingest Workflow

When the user adds a new source:

1. **Put cleaned Markdown in `Raw/Sources/`.** Clean the content thoroughly — remove navigation, ads, sidebar links, footer text. For video transcripts: strip timestamps (`**0:08** ·`, `**14:14** ·`), filler words (`you know`, `eh?`, `[snorts]`, `[music]`), social media handles/hashtags, subscribe prompts. Preserve all factual claims, data points, technical explanations, paper names/authors/institutions/dates, quantitative results. The cleaned source should read like a structured article — not timestamped dialogue.

2. **Search the catalog for related topics.**
   ```bash
   python3 scripts/wiki_tool.py search-catalog --query "key topic"
   ```

3. **Open only the most relevant compiled Wiki notes** from Step 2 results — not all Raw context. Understand what already exists before creating new notes.

4. **Create or update focused notes in `Wiki/`** (correct folder per tag):
   - Topic notes → `Wiki/Topics/`
   - Concept notes → `Wiki/Concepts/`  
   - Entity notes → `Wiki/Entities/`
   - Project notes → `Wiki/Projects/`

5. **Add Raw source links to `sources`.** Keep `source_count` accurate (must equal number of entries in `sources`).

6. **Run validation:**
   ```bash
   python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint
   ```

7. **Update manifest:** `python3 scripts/wiki_tool.py source-scan --update --accept-covered`
   This validates that all wiki notes in `covered_by` still exist on disk and removes stale entries automatically.

8. **Add a log entry** if the ingest meaningfully changed the Wiki:
   ```bash
   python3 scripts/wiki_tool.py log --title "..." --details "..."
   ```

9. **Commit.** The pre-commit hook runs `build + lint + source-lint` automatically. If any check fails, fix the issues before committing.

> **Note:** The setup wizard auto-runs `git init` on first setup. If this is a new repo, configure your remote first: `git remote add origin <url>` then `git push -u origin main`. For private repos, `touch .private-repo` to skip public security scans on push.

## Query Workflow

When answering a question from the Wiki:

1. Start with `Wiki/index.md` for an overview.
2. Search the catalog:

```bash
python3 scripts/wiki_tool.py search-catalog --query "user topic"
```

3. Open the most relevant Wiki notes from Step 2 results.
4. Synthesize an answer from the compiled notes (distilled knowledge).
5. Open Raw sources **only** when:
   - The compiled note is insufficient, OR
   - Source-level verification is requested.
6. Cite both the compiled note and Raw source when your answer depends on source material.

## Maintenance Gate

Before every meaningful commit, run:

```bash
python3 scripts/wiki_tool.py doctor && python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint
```

After source ingestion, also run:

```bash
python3 scripts/wiki_tool.py source-scan --update --accept-covered && python3 scripts/wiki_tool.py source-lint
```

## Security Audit (Before Push to Public Repos)

**When:** Before pushing changes to a public repository (e.g., the installer repo).

1. **Run fast security scan:**
   ```bash
   python3 scripts/wiki_tool.py security-scan --mode public
   ```
2. **Run full compliance audit:**
   ```bash
   python3 scripts/wiki_tool.py audit --mode public
   ```
3. **Fix critical findings** before pushing (secrets, tokens, private keys).
4. **Review warnings** at your convenience (broken wikilinks, orphaned notes).

For private repositories, run with `--mode private` — this skips local path detection (which is expected in wiki notes).

Add a `.private-repo` marker file to the repo root if you want tools to skip public-mode checks.

## Scripts Reference

| Command | Purpose |
|---------|---------|
| `python3 scripts/wiki_tool.py doctor` | Non-mutating health check (folders, Python version, catalog, manifest) |
| `python3 scripts/wiki_tool.py build` | Rebuilds `catalog.jsonl`, `index.md`, and per-folder indexes |
| `python3 scripts/wiki_tool.py lint` | Validates compiled note frontmatter, tags, source links, `source_count` |
| `python3 scripts/wiki_tool.py source-scan [--update] [--accept-covered]` | Lists Raw sources; `--update` updates manifest (deduplicates apostrophe-normalized entries); `--accept-covered` marks covered as processed and validates all wiki notes in `covered_by` still exist on disk |
| `python3 scripts/wiki_tool.py source-lint` | Validates source frontmatter and coverage state |
| `python3 scripts/wiki_tool.py search-catalog --query "text"` | Searches compiled Wiki notes via `catalog.jsonl` |
| `python3 scripts/wiki_tool.py log --title "t" --details "d"` | Appends a short entry to `Wiki/Logs/log.md` |
| `python3 scripts/wiki_tool.py security-scan [--mode public|private]` | Fast secrets-only scan of tracked files (exit 0 = clean, exit 1 = critical) |
| `python3 scripts/wiki_tool.py audit [--mode public|private]` | Full security + wiki compliance scan: secrets, broken wikilinks, orphaned notes, coverage gaps (exit 0 = clean, exit 1 = critical, exit 2 = warnings) |

## Obsidian CLI (Optional — Requires Running Obsidian)

The `obsidian` CLI provides features no other tool can do. Only use when Obsidian is running.

| Command | Purpose |
|---------|--------|
| `obsidian vault="<vault_name>" unresolved` | Lists broken/missing wikilinks in the vault |
| `obsidian vault="<vault_name>" tasks` | Lists all checkbox tasks across notes |
| `obsidian vault="<vault_name>" daily:read` | Reads the current daily note |

> **Rule:** If Obsidian is not running, do NOT use the CLI for note CRUD — fall back to built-in `obsidian_*` functions or bash.
