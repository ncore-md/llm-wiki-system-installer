
# Query & Maintenance Workflows

**Query read path, maintenance pipeline, and lint pre-commit gate.**

---

## Query Workflow (Read Path)

When the user asks a question that could be answered from the Wiki knowledge base:

```
  User Question                                                                                                  
          │                                                                                                      
          ▼                                                                                                      
  ┌───────────────┐                                                                                              
  │ Pre-flight    │ ← config check → vault selection                                                             
  │ Check         │   (same as ingest)                                                                           
  └───────┬───────┘                                                                                              
          │                                                                                                      
  ┌───────▼───────────────┐                                                                                      
  │ 1. Read Wiki/index.md │ ← overview of available knowledge                                                    
  └───────┬───────────────┘                                                                                      
          │                                                                                                      
  ┌───────▼───────────────┐                                                                                      
  │ 2. Search Catalog     │ ← wiki_tool.py search-catalog --query "..."                                          
  └───────┬───────────────┘                                                                                      
          │ (top matches)                                                                                        
  ┌───────▼───────────────┐                                                                                      
  │ 3. Read Relevant Notes │ ← obsidian read on matched notes                                                    
  └───────┬───────────────┘                                                                                      
          │                                                                                                      
  ┌───────▼───────────────┐                                                                                      
  │ 4. Synthesize Answer   │ ← distilled knowledge from compiled notes                                           
  └───────┬───────────────┘                                                                                      
          │ (only if insufficient)                                                                               
  ┌───────▼───────────────┐                                                                                      
  │ 5. Fall back to Raw    │ ← original sources for verification                                                 
  └───────────────────────┘                                                                                      
```

### Core Rules During Query
- Always search the catalog before reading Raw sources directly.
- Prefer compiled Wiki notes over raw source material — they are pre-distilled and structured.
- If the catalog returns no results, inform the user that the topic may not be in this wiki yet.
- Never invent information — only report what is found in the notes or sources.
- Cite both compiled note and Raw source when your answer depends on source material.

### Pre-flight & Vault Selection (Same as Ingest)
1. **Check config:** `python3 scripts/wiki_shared.py vaults 2>&1`
   - If output lists vaults → proceed to Vault Selection
   - If empty or "No project config" → offer setup: spawn subagent with `llm-wiki-setup` skill

2. **Vault Selection:**
   - Check invocation arguments for vault name(s) first (space-separated, `all` = every declared vault)
   - Single-vault shortcut: if pre-flight returns exactly one vault, skip selection and use it directly
   - Validate every chosen vault is declared in config. Wrong names stop the operation.

---

## Maintenance Workflow (Broader Than Lint)

Before a meaningful commit that touches Wiki content, or when the user asks you to run maintenance on the wiki:

```bash
python3 scripts/wiki_tool.py doctor && python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint
```

### Step-by-Step

1. **Health check:** `python3 scripts/wiki_tool.py doctor`
   - Validates: Python version (3.8+), required dirs exist, catalog exists, manifest exists
   - Reports: Wiki note count and Raw source count

2. **Rebuild catalog and index:** `python3 scripts/wiki_tool.py build`
   - Rebuilds `catalog.jsonl`, `index.md`, and per-folder indexes from all wiki notes
   - Auto-fixes curly apostrophes in source paths (U+2019 → U+0027)
   - Auto-fixes empty `sources: []` arrays by populating from body text under `## Sources:`

3. **Validate compiled notes:** `python3 scripts/wiki_tool.py lint`
   - Validates: tag validity, dates (YYYY-MM-DD), source paths resolve on disk, `source_count` consistency
   - Validates: required sections present (## Related AND ## Sources) — missing either fails the check
   - Validates: topics consistency for concept/entity notes (≥1 topic, ≤max_topics from AGENTS.md rules)

4. **Check Raw source coverage:** `python3 scripts/wiki_tool.py source-lint`
   - Validates: raw source frontmatter (title, reference/source present, created date format)
   - Validates: coverage state (processed sources must have `covered_by` entries)

5. **Log changes** if the maintenance cycle modified Wiki content:
   ```bash
   python3 scripts/wiki_tool.py log --title "Maintenance" --details "<what was affected and why>"
   ```

6. **Report results** — all checks must pass before committing. If any fail, fix the issues first.

---

## Lint Workflow (Focused Pre-commit Gate)

When the user asks to check wiki quality, before committing changes that affect Wiki notes, or after creating/editing a note:

### Step-by-Step
1. **Identify the wiki root** for the selected vault (see Pre-flight & Vault Selection above).

2. **Read AGENTS.md** from the wiki root to get:
   - Allowed tags for compiled notes (from "Allowed Tags" section)
   - Required frontmatter fields (from Schema/frontmatter-schema.md)
   - Structured rules from `---checklist---` section via:
     ```bash
     python3 -c "from wiki_shared import parse_rules; print(json.dumps(parse_rules('.'), indent=2))"
     ```

3. **Check frontmatter on each Wiki note:**
   - `tags` array exists and contains one of the allowed tags for compiled notes (from AGENTS.md — NOT hardcoded)
   - `topics` and `sources` arrays are present (even if empty: `[]`)
   - Dates (`created`, `updated`) in YYYY-MM-DD format

4. **Check source_count:** must equal the number of entries in `sources` array (derived, not manually set)

5. **Run programmatic validation:**
   ```bash
   python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint
   ```

6. **Report any issues** found with file names and specific violations. Fix lint failures before committing — never commit past a failed lint.

---

## Maintenance Gate (Before Every Meaningful Commit)

```bash
python3 scripts/wiki_tool.py doctor && python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint
```

After source ingestion, also run:
```bash
python3 scripts/wiki_tool.py source-scan --update --accept-covered && python3 scripts/wiki_tool.py source-lint
```

---

## Daily Workflow (from original design)

```
1. Add source material to Raw/Sources/
2. Compile short reusable notes in Wiki/ (ingest pipeline, Steps 0–9)
3. Rebuild indexes and Wiki/catalog.jsonl (wiki_tool.py build)
4. Run lint and source checks (wiki_tool.py lint + wiki_tool.py source-lint)
5. Append Wiki/log.md with changes (wiki_tool.py log --title "..." --details "...")
```

---

## Comparison: Maintain vs Lint

| Aspect | **Maintain** (broader) | **Lint** (focused) |
|---|---|---|
| Scope | Full health cycle: doctor → build → lint → source-lint | Focused validation of frontmatter & schema |
| Rebuilds catalog | Yes (`build`) — regenerates indexes from all notes | No (assumes current) |
| Health check | Yes (`doctor`) — Python version, dirs, file existence | No |
| Source coverage | Full `source-lint` check on all raw sources & manifest | Runs source-lint too, but as part of validation chain |
| Logging | Yes — logs maintenance changes to Wiki/Logs/log.md | No (reports issues, doesn't log) |
| Use case | Periodic maintenance or before meaningful commits | Quick quality check after note creation/editing |
| Result | Reports + fixes (auto-fixes in build) | Reports issues only — doesn't fix |

---

## Security Audit (Separate from Maintain/Lint)

The audit skill is **not part of the maintain or lint workflows** — it addresses a different concern: security and compliance rather than schema quality.

| Aspect | **Audit** (security) | **Maintain** (health) | **Lint** (quality) |
|---|---|---|---|
| Focus | Secrets exposure, broken refs, orphans | System state, catalog freshness | Frontmatter correctness |
| Scans files for secrets | Yes (API keys, tokens, private keys) | No | No |
| Checks broken wikilinks | Yes (all tracked files) | Partially (via build) | No |
| Detects orphaned notes | Yes | No | No |
| Source coverage gaps | Yes (manifest-based) | Partially (`source-lint`) | Via `source-lint` |
| Exit codes block push | Critical findings = exit 1 (blocks) | Never blocks | Reports only |
| When to run | Before push to public repos | Before meaningful commits | After note creation/editing |
| Mode sensitivity | `--mode public` / `--mode private` affects path scan | None | None |

---

> **See also:**
> - [[system-overview]] — High-level architecture, directory layout, design principles  
> - [[entity-hierarchy-data-flow]] — Entity hierarchy, tag routing, frontmatter contract
> - [[shared-infrastructure]] — wiki_tool.py commands in detail (build, lint, source-scan)
> - [[ingest-pipeline]] — Complete ingest pipeline (Steps 0–9) with mandatory checklist
