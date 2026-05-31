
# LLM Wiki System — Overview

**High-level architecture, two-layer structure, and directory layout.**

---

## Two-Layer Structure

```
  ┌─────────────────────────────────────────┐                                                            
  │  PROJECT ROOT (.llm-wiki-config/config.json)    │ ← Per-project: vault declarations, permissions             
  ├─────────────────────────────────────────┤                                                            
  │  SHARED WIKI SYSTEM (.llm-wiki/Core/)           │ ← Read-only framework shared across projects               
  └─────────────────────────────────────────┘                                                            
```

The config is the **single source of truth** for which vaults a project can access and with what permissions. The shared wiki system contains all skills, tooling, templates, rules, and compiled knowledge.

> **See also:**
> - [[entity-hierarchy-data-flow]] — Entity hierarchy, data flow between layers, tag routing, frontmatter contract
> - [[shared-infrastructure]] — Shared infrastructure (wiki_shared.py, wiki_tool.py), external tools
> - [[ingest-pipeline]] — Complete ingest pipeline (Steps 0–9) with mandatory checklist, audit as Step 10
> - [[query-maintenance]] — Query read path, maintenance and lint workflows, security audit comparison
> - [[llm-wiki-audit]] — Security & compliance: secrets, broken refs, orphans, coverage gaps

---

## Directory Structure

```
  <wiki-root>/                                                                                                   
  ├── AGENTS.md           # Vault rules, checklist system (rules engine)                                           
  ├── README.md           # System documentation                                                                   
  ├── _templates/         # Note templates (concept, entity, topic, project, source)                               
  ├── Raw/Sources/        # Source-faithful cleaned content (markdown, images)                                     
  ├── Raw/Files/          # Binary attachments (images, PDFs)                                                      
  ├── Wiki/               # Compiled wiki notes:                                                                   
  │   ├── Topics/         # Broad subject areas (leaf nodes, topics: [])                                           
  │   ├── Concepts/       # Discrete ideas, definitions (topics_required_for)                                      
  │   ├── Entities/       # People, organizations, tools                                                           
  │   └── Projects/       # Initiatives with scope & status                                                        
  ├── Wiki/Logs/log.md    # Activity log (no frontmatter)                                                          
  ├── Schema/             # Cache files, rules, lint checklist                                                     
  │   └── .llm-wiki-cache.json # Shared state (defaults, VL results, discovered config)                           
  ├── scripts/            # wiki_tool.py, wiki_shared.py                                                           
  └── .agents/skills/     # 7 skills (ingest, lint, maintain, setup, vl, query, audit)                                    
```

---

## Two Distinct Tag Domains (Critical)

**Source Notes (`Raw/Sources/`):**
- `tags: [source]` — exactly one tag, purely an identifier (never used for routing)
- Type metadata goes in `ContentType` field: `[video]`, `[article]`, `[markdown]`, `[pdf]`
- `Processed: false/true` boolean tracks compilation status

**Compiled Wiki Notes (`Wiki/`):**
- `tags: [concept]` or `[topic]` or `[entity]` or `[project]` — exactly ONE role tag
- Routing is determined by the tag value → folder mapping in AGENTS.md's `tag_routing`

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
