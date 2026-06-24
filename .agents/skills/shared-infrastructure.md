
# Shared Infrastructure & Dependencies

**wiki_shared.py, wiki_tool.py, external tools, and the design principles that make it all work.**

---

## Shared Infrastructure (Not Skills)

These are not skills themselves but support all of them:

| Component | Purpose |
|---|---|
| **`wiki_shared.py`** | Config discovery, VL discovery (`discover_vl_models()`), model resolution (`resolve_model(task)`), project config management, rules parsing, cache management |
| **`wiki_tool.py`** | `build`, `lint`, `source-lint`, `search-catalog`, `source-scan`, `log`, `doctor` — schema enforcement Obsidian doesn't know about. **New: `security-scan`, `audit`** — security & compliance scanning for secrets, broken wikilinks, orphaned notes, and source coverage gaps |
| **`.llm-wiki-cache.json`** | Shared state: discovered config, defaults (VL/text models), VL discovery results, task overrides. Auto-refreshed when AGENTS.md changes via mtime detection. |
| **`audit-rules.json`** | Configurable security scan patterns (secrets, paths to skip). Optional — uses built-in defaults if missing. Stored in `.llm-wiki-config/`. |
| **Schema/** | `frontmatter-schema.md` (field types), `lint-checklist.md`, `naming-conventions.md` |
| **_templates/** | Per-tag templates: concept-note, entity-note, topic-note, project-note, log-note, source-note |
| **AGENTS.md checklist** | Per-vault rules parsed from `---checklist---` YAML block: max_topics, required_sections, allowed_tags, tag_routing, topics_required_for |

---

## wiki_shared.py — Shared Utilities (`1509 lines`)

### Config Discovery
- **`discover_config(wiki_root, force=False)`** — Discovers wiki structure from AGENTS.md + directory layout. Populates cache with tag_routing, allowed_compiled_tags, paths, vaults. Stale detection based on AGENTS.md mtime vs `discovered_at` timestamp. Auto-refreshes raw_paths from actual directories even when skipping full discovery.
- **`parse_rules(wiki_root, rules_path_rel="AGENTS.md")`** — Parses YAML block between `---checklist---` markers in AGENTS.md. Returns max_topics, required_sections, allowed_tags, tag_routing, topics_required_for, source_tag, allowed_content_types. Falls back to basic parser if PyYAML unavailable.
- **`_discover_tag_routing(wiki_root)`** — Resolution order: (1) `tag_routing` from AGENTS.md checklist, (2) Directory Structure table in AGENTS.md using standard map, (3) Scan actual Wiki/ subdirectories as fallback.
- **`_discover_raw_source_dirs(wiki_root)`** — Scans all immediate children of Raw/ for directories containing markdown files with frontmatter. Returns relative paths like `["Raw/Sources"]`.
- **`_discover_source_tags(wiki_root)`** — Returns `['source']` from AGENTS.md checklist.
- **`_discover_content_types(wiki_root)`** — Returns allowed content types from AGENTS.md checklist.

### Project Config Management
- **`find_project_config(wiki_root=None)`** — Walks up from wiki root looking for `.llm-wiki-config/`.
- **`load_project_config(wiki_root=None)`** — Reads and validates `config.json`. Checks vaults exist, permissions are valid (`read`, `write`, `ingest`, `maintain`).
- **`get_project_config_path(wiki_root=None)`** — Returns the config file path or None.

### Model Resolution
- **`resolve_model(task, cache_path=None)`** — Resolves which model to use for a task. `image_ingest`/`video_analysis` → VL models (provider, model_id, base_url). `note_generation` → text model. Reads from project config first (source of truth), falls back to cache defaults.
- **`set_default(field, value)`** — Sets a shared default in both cache and project config. Persists VL/text fields to `config.json`.
- **`set_task_override(task, field, value)`** — Sets per-task overrides in cache (e.g., `image_ingest.vl_model_id`).

### VL Discovery
- **`discover_vl_models(cache_path=None, force=False)`** — Reads `~/.pi/agent/models.json` to find all VL-capable models across registered providers. Checks if pi's current model has native vision (checks `known_current_models` like `qwen3.6-35b-a3b-oQ6`). Returns `{agent_has_vision, provider, model_id, base_url}`. Results cached to avoid repeated discovery.

### Cache Management
- **`get_cache_path(wiki_root=None)`** — Returns `WikiRoot/Schema/.llm-wiki-cache.json`. Auto-detects wiki root from cwd (looks for Schema/ + Wiki/).
- **`load_cache()` / `save_cache(data)`** — Load/save with forward compatibility (ensures all default keys exist).

### CLI Entry Points
```bash
python3 scripts/wiki_shared.py find-project-config    # Print config dir or "not found"
python3 scripts/wiki_shared.py discover [--force]      # Run VL discovery
python3 scripts/wiki_shared.py vaults                  # List declared vaults + permissions
python3 scripts/wiki_shared.py models <task>           # Show resolved model for task
python3 scripts/wiki_shared.py set-default <field> <value>  # Set a default
python3 scripts/wiki_shared.py set-override <task> <field> <value>  # Set task override
python3 scripts/wiki_shared.py status                  # Show full cache state
python3 scripts/wiki_shared.py config [--force]        # Discover wiki structure + project config
```

---

## wiki_tool.py — Validation & Tooling (`1289 lines`)

### Commands

| Command | Purpose |
|---------|---------|
| `doctor` | Health check: Python version (3.8+), required dirs, catalog exists, manifest exists |
| `build` | Rebuilds `catalog.jsonl`, `index.md`, per-folder indexes. Auto-fixes curly apostrophes and empty sources[] |
| `lint` | Validates compiled note frontmatter: tag validity, source_count matches sources length, each source path resolves on disk, required sections present (## Related + ## Sources), topics consistency for concept/entity notes, date format YYYY-MM-DD |
| `source-scan [--update] [--accept-covered]` | Lists raw sources with processed/covered status. `--update` updates manifest (deduplicates curly apostrophe variants, removes stale paths). `--accept-covered` marks covered sources as processed and validates all covered_by entries exist on disk |
| `source-lint` | Validates raw source frontmatter (Title, Reference present, Created date format, tags must be [source], ContentType valid), checks processed sources have coverage |
| `search-catalog --query "text"` | Word-level matching on title, topics, tags, sources fields in catalog.jsonl. Any query term triggers a match |
| `log --title "t" --details "d"` | Appends timestamped entry to Wiki/Logs/log.md |
| `fix-frontmatter` | Auto-corrects YAML type mismatches (scalar ↔ array) using PyYAML with block-style dumper |
| `normalize-apostrophes` | Renames files with curly apostrophes (U+2019 → U+0027) in Raw/ and updates all references |
| `source-delta` | Shows raw sources not in manifest (actionable) and manifest entries with no Raw source (cleanup candidates) |

### Internal Mechanics

**YAML Parser (`yaml_parse()`):** Custom parser (stdlib only, no PyYAML dependency). Handles block arrays (`tags:\n  - concept`), inline arrays (`["a", "b"]`), and scalars. Used consistently by lint/build/source-scan for deterministic parsing.

**Apostrophe Normalization:** `_normalize_curly_apostrophe()` replaces U+2019 (curly) with U+0027 (straight). Applied in `normalize_raw_sources()` for Raw/ filenames and frontmatter, plus `_normalize_wiki_source_paths()` for all wiki note references.

**Auto-fix Empty Sources (`_fix_empty_sources()`):** During `build`, automatically populates empty `sources: []` arrays from body text under `## Sources:`. This is a safety net, not a substitute for proper frontmatter — always fill sources in YAML before writing.

**Lint Validation Flow:**
1. Parse vault rules from AGENTS.md via `parse_rules()` (fallback to hardcoded defaults)
2. For each wiki note: validate tag, source_count matches sources length, source paths resolve on disk
3. Check required sections present (## Related + ## Sources)
4. Validate topics consistency: concept/entity notes must have ≥1 topic (≤max_topics from rules)
5. Validate date format YYYY-MM-DD

---

## External Tool Dependencies

| Tool | Used By | Purpose |
|---|---|---|
| **obsidian CLI** (`$OBSIDIAN_CLI` or `obsidian`) | ingest, query, setup, lint, maintain | Vault CRUD via Chrome DevTools Protocol — read/write/search notes & properties. All vault file operations go through this or native `obsidian_write`/`obsidian_append`. |
| **defuddle** | ingest (Step 1 — URL cleaning) | Extract clean markdown from web pages, removing navigation/ads/clutter. Only deterministic noise removal; ALL factual content preserved in source-faithful layer. |
| **obsidian_write / obsidian_append** (native) | ingest, query | Structured note creation — preferred over CLI for YAML frontmatter safety. Pass content as structured params, no shell escaping issues. |

---

## Key Design Principles (Why It Works)

1. **Source-faithful Raw layer** — raw content is never modified during compilation; only cleaned of noise (timestamps, promo). Distillation happens in compiled Wiki notes. Source cleaning = deterministic noise removal only; editorial distillation belongs exclusively in compiled note creation (Steps 2–9).

2. **Catalog-driven search** — `catalog.jsonl` is a structured index (title, tags, topics, sources). Query always uses catalog first via `search-catalog`, not raw Obsidian search or full-text scans.

3. **Lint as safety gate** — Python scripts enforce schema rules Obsidian doesn't know about (source resolution, `source_count` consistency, required sections). Pre-commit hook catches anything missed.

4. **Config-driven paths** — skills discover from `config.json` → cache, enabling multi-vault support with independent raw paths and per-vault tag routing. The `tag_routing` is discovered from AGENTS.md's checklist (priority 1), Directory Structure table (priority 2), or Wiki/ subdirectory scanning (fallback).

5. **CDP-only writes** — all vault operations use `obsidian_write`/`obsidian_append`, never raw filesystem I/O on vault files (risk of YAML corruption, broken wikilinks).

6. **Mandatory checklist** — ingest has 12+ verification checkpoints (C0–C11) that must pass before proceeding. Empty sources, missing sections, or format violations block the pipeline.

7. **Source-to-note traceability** — every compiled note links back to Raw sources via `sources` + `source_count`. The manifest tracks which notes each source produced (`covered_by`).

8. **Per-vault tag routing** — different vaults can have completely different folder structures for the same tags, discovered from each vault's AGENTS.md.

---

> **See also:**
> - [[system-overview]] — High-level architecture, directory layout
> - [[entity-hierarchy-data-flow]] — Entity hierarchy, data flow between layers, frontmatter contract
> - [[ingest-pipeline]] — Complete ingest pipeline (Steps 0–9) with mandatory checklist
> - [[query-maintenance]] — Query read path, maintenance and lint workflows
