
# Entity Hierarchy & Data Flow

**The complete data layer: config → rules → tag routing → raw/compiled layers → catalog.**

---

## Entity Hierarchy (Data Flow)

```
  CONFIG (.llm-wiki-config/config.json)                                                                          
    │                                                                                                            
    ├── Declares vaults with permissions: [read, write, ingest, maintain]                                         
    │   Core: [read, write, ingest, maintain]     ← primary wiki                                                 
    │   NLite: [read]                             ← read-only reference                                          
    └────────────────────────────────────────────────┘                                                           
                      │                                                                                          
           ┌──────────▼──────────┐                                                                               
           │  AGENTS.md          │ ← Per-vault rules: tag_routing, allowed_tags,                                 
           │  (rules engine)     │   required_sections, max_topics, source_tag                                   
           └──────────┬──────────┘                                                                               
                       │ discovered by parse_rules()                                                               
           ┌──────────▼──────────┐                                                                               
           │  TAG ROUTING        │ ← Maps tags → folders (per-vault)                                             
           │                     │   topic    → Wiki/Topics/                                                     
           │                     │   concept  → Wiki/Concepts/                                                   
           │                     │   entity   → Wiki/Entities/                                                   
           │                     │   project  → Wiki/Projects/                                                   
           │                     │   log      → Wiki/Logs/log.md                                                 
           └──────────┬──────────┘                                                                               
                       │ dictates placement                                                                       
           ═══════════╪═════════════════════════════════                                                         
                       │                                                                                          
           ┌──────────▼──────────┐        ┌───────────────┐                                                      
           │  RAW LAYER          │        │ SCHEMA       │                                                      
           │                     │        │               │                                                      
           │ Raw/Sources/        │───────►│ source-manifest.jsonl  │                                             
           │ (source-faithful)   │ tracks coverage    │                                                          
           │                     │        └───────────────┘                                                      
           │ Raw/Files/          │◄───────►│               │                                                     
           │ (images, PDFs)      │  covered_by    │                                                              
           └──────────┬──────────┘        └───────▲───────┘                                                      
                       │ compiled into              │ validates                                                   
           ┌──────────▼──────────┐        ┌───────┴───────┐                                                      
           │  WIKI LAYER         │        │ FRONTMATTER   │                                                      
           │                     │◄───────│ CONTRACT      │                                                      
           │ Wiki/Topics/        │  tag   │               │                                                     
           │ Wiki/Concepts/      │ routing│ tags: array    │                                                     
           │ Wiki/Entities/      │ & rules│ topics ≥1     │                                                      
           │ Wiki/Projects/      │       │ sources: array │                                                      
           │ Wiki/Logs/log.md    │       │ source_count   │                                                      
           └──────────┬──────────┘       │ dates: YYYY-MM-DD│                                                    
                       │ indexed into      └───────▲─────────┘                                                   
           ┌──────────▼──────────┐        └────────┤                                                             
           │  CATALOG            │                  │ parsed by                                                  
           │ catalog.jsonl       │──────────────────┘                                                            
           │ index.md            │  read by query skill                                                          
           └─────────────────────┘                                                                               

SHARED CACHE: Schema/.llm-wiki-cache.json
  config (discovered from AGENTS.md + directory scan)
    wiki_name, tag_routing, allowed_compiled_tags, raw_source_dirs, rules (parsed checklist)
  defaults (user-configurable VL/text models, agent_has_vision flag)
  task_overrides (per-task model overrides: image_ingest, video_analysis, note_generation)
  vl_discovery (discovered VL models from ~/.pi/agent/models.json)

── Discovered at runtime by wiki_shared.py discover_config() ──
  Stale detection: AGENTS.md mtime vs discovered_at timestamp. 
  Auto-refreshes raw_paths from actual directories even when skipping full discovery.
──

```


## Note Type Relationships (Compiled Wiki Graph)

Each compiled note is a node in a directed graph:

```
  [Topic Note]  ◄── topics ── [Concept Note]                                                                     
                             ▲   (wikilinks to topic)                                                             
                             │ sources ──► [Raw Source]                                                           
                       [Entity Note] ◄──┘                                                                         
                             │ sources ──► [Raw Source / Image File]                                              
                                                                                                                  
  [Project Note] ◄── topics ──┘                                                                                  
```

- **Topics** are leaf nodes — `topics: []` (no parents)
- **Concepts/Entities** reference ≥1 topic via `topics: [[Topic Name]]` (enforced by lint)
- **Projects** follow the same pattern as concepts/entities but are NOT in `topics_required_for`
- All notes trace back to Raw sources via `sources` + `source_count`


## Frontmatter Contract (Block-Style Required)

### Source Notes (`Raw/Sources/`)

```yaml
---
Title: "Source title"
Author: ""
Reference: "URL or origin identifier"
ContentType:
  - "markdown"   # video | article | markdown | pdf
Created: YYYY-MM-DD
Processed: false
tags:
  - "source"     # exactly one — identifier, never used for routing
---

# Source content follows (source-faithful)
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `Title` | Yes | string | Human-readable title of the source. |
| `Author` | No | string or array | Author name(s). Can be empty. |
| `Reference` | Yes | string | URL, file path, or identifier for the original source. |
| `ContentType` | Yes | array of strings | One or more: `"markdown"`, `"video"`, `"audio"`, `"pdf"`. |
| `Created` | Yes | string (date) | Date the source was created or published. YYYY-MM-DD format. |
| `Processed` | No | boolean | Whether this source has been compiled into Wiki notes. Default: false. |
| `tags` | Yes | array of strings | Must include `"source"`. May also include custom tags. |

### Compiled Wiki Notes (`Wiki/`) — Topic, Concept, Entity, Project

```yaml
---
tags:
  - "concept"           # Exactly one: topic | concept | entity | project (not log)
topics:                 # Parent topics — wikilinks to Wiki/Topics/
  - [[Existing Topic]]  # At least one for concept/entity (topics_required_for)
status: seed            # seed | active | canonical | stale | needs_review
created: YYYY-MM-DD     # Date the note was first created.
updated: YYYY-MM-DD     # Last update date. YYYY-MM-DD format.
sources:                # Wikilinks to Raw sources (must exist on disk)
  - "[[Raw/Sources/example-source.md]]"
source_count: 1         # Must equal len(sources) — derived, not manually set.
aliases: []             # Alternative names for this note (optional).
---

# Title + short summary paragraph(s)

## Key Points / Scope / Goal (content-specific heading)
- bullet points or paragraphs

## Related
- [[Related Note]]

## Sources
- [[Raw/Sources/example-source.md]]  ← display only, does NOT populate frontmatter
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `tags` | Yes | array of strings | Exactly one from: `"topic"`, `"concept"`, `"entity"`, `"project"` (not `log`). |
| `topics` | Yes | array of strings | Parent topic(s). Can be empty for top-level topics. Use wikilinks `[[Topic Name]]`. |
| `status` | No | string | Note maturity. Default: `"seed"`. |
| `created` / `updated` | Yes | string (date) | YYYY-MM-DD format. |
| `sources` | Yes | array of strings | Wikilinks to Raw sources in YAML frontmatter. Body `## Sources` does NOT populate this. |
| `source_count` | Yes | integer | Must equal the length of `sources`. Validated by lint. |
| `aliases` | No | array of strings | Alternative names for search and linking. Can be empty. |

### Log Notes (`Wiki/Logs/log.md`)
Log notes do not use front matter — they are plain markdown with structured entries:

```markdown
# Wiki Activity Log

## [YYYY-MM-DD HH:MM] Brief description of change

Details about what changed, why, and what files were affected.
```


## Naming Conventions

- **File names:** lowercase with hyphens: `knowledge-graphs.md`, not `Knowledge Graphs.md`
- **Note titles (frontmatter):** Title Case: `Graph RAG`, not `graph rag`
- **Wikilinks:** Title Case display names: `[[Knowledge Graphs]]`, not file paths
- **Tags:** lowercase with hyphens: `knowledge-graphs`


> **See also:**
> - [[system-overview]] — High-level architecture, directory layout
> - [[shared-infrastructure]] — wiki_tool.py lint rules, frontmatter validation details, audit commands
> - [[ingest-pipeline]] — How notes are created from sources (Steps 0–9), security audit as Step 10
> - [[llm-wiki-audit]] — Security & compliance: secrets, broken refs, orphans, coverage gaps
