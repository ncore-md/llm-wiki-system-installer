# Front Matter Schema

All notes in the LLM Wiki must follow consistent front matter. This is the contract between you and your agentic AI — every note follows these rules so that scripts, lint checks, and catalog searches work reliably.

Related: [[Schema/naming-conventions.md]], [[Schema/lint-checklist.md]], [[AGENTS.md]]

## Source Notes (`Raw/Sources/`)

```yaml
---
Title: "Source title"
Author: ""
Reference: "URL or origin identifier"
ContentType:
  - "markdown"
Created: YYYY-MM-DD
Processed: false
tags:
  - "source"
---
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `Title` | Yes | string | Human-readable title of the source. |
| `Author` | No | string or array | Author name(s). Can be empty. |
| `Reference` | Yes | string | URL, file path, or identifier for the original source. |
| `ContentType` | Yes | array of strings | One or more: `"markdown"`, `"video"`, `"audio"`, `"pdf"`. |
| `Created` | Yes | string (date) | Date the source was created or published. YYYY-MM-DD format. |
| `Processed` | No | boolean | Whether this source has been compiled into Wiki notes. Default: false. |
| `tags` | Yes | array of strings | Must include `"source"`. May also include `"clippings"` or custom tags. |

## Compiled Wiki Notes (`Wiki/`)

### Topic, Concept, Entity, Project Notes

```yaml
---
tags:
  - "concept"
topics: []
status: seed
created: YYYY-MM-DD
updated: YYYY-MM-DD
sources: []
source_count: 0
aliases: []
---
```

| Field | Required | Type | Notes |
|-------|----------|------|-------|
| `tags` | Yes | array of strings | Exactly one: `"topic"`, `"concept"`, `"entity"`, or `"project"`. |
| `topics` | Yes | array of strings | Parent topic(s) this note relates to. Can be empty for top-level topics. Use wikilinks `[[Topic Name]]`. |
| `status` | No | string | Note maturity: `"seed"`, `"active"`, `"canonical"`, `"stale"`, or `"needs_review"`. Default: `"seed"`. |
| `created` | Yes | string (date) | Date the note was first created. YYYY-MM-DD format. |
| `updated` | Yes | string (date) | Last update date. YYYY-MM-DD format. |
| `sources` | Yes | array of strings | Wikilinks to Raw sources, e.g. `[Raw/Sources/example-source.md]`. Actual format in notes uses double-bracket wikilinks: `[[Raw/Sources/example-source.md]]`. |
| `source_count` | Yes | integer | Must equal the length of `sources`. Used by lint checks. |
| `aliases` | No | array of strings | Alternative names for this note (for search and linking). Can be empty. |

### Log Notes (`Wiki/Logs/log.md`)

Log notes do not use front matter — they are plain markdown with structured entries.

```markdown
# Wiki Activity Log


## [YYYY-MM-DD HH:MM] Brief description of change

Details about what changed, why, and what files were affected.
```

## Rules

- All dates must be in `YYYY-MM-DD` format.
- `source_count` MUST equal the number of entries in `sources`. Lint will fail if they mismatch.
- Every compiled Wiki note must link to at least one Raw source in `sources`.
- Tags must be exactly one of the allowed values: `"topic"`, `"concept"`, `"entity"`, `"project"`.
- Source paths in `sources` must exist under `Raw/Sources/`.
