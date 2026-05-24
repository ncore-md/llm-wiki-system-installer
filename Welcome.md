# Welcome to Your LLM Wiki

This is a structured knowledge base for agentic AI. The system turns raw source material into organized, queryable knowledge that grows over time.

## Quick Start

1. **Add sources** — Place cleaned Markdown in `[[Raw/Sources/]]`
2. **Ingest** — Follow the ingest workflow in [[AGENTS.md]] to compile notes into `[[Wiki/]]`
3. **Query** — Search the catalog and read compiled notes for answers

## System Files

| File | Purpose |
|------|---------|
| [[AGENTS.md]] | Agent instructions, workflow reference, tooling guide |
| `[[Wiki/index.md]]` | Compiled knowledge index — start here for search |
| [[Schema/frontmatter-schema.md]] | Frontmatter rules and validation definitions |
| `[[_templates/]]` | Note templates (concept, entity, topic, project, log) |
| [[scripts/wiki_tool.py]] | Validation tools (build, lint, search-catalog) |
| `.agents/skills/` | Agent skills (ingest, query, lint, maintain) |

## Directory Structure

| Path | Role |
|------|------|
| `Raw/Sources/` | Source material (transcripts, articles) — never modify after ingestion |
| `Wiki/` | Compiled knowledge (topics, concepts, entities) — this is your knowledge base |
| `Schema/` | Rules and schemas that enforce consistency |
| `_templates/` | Note templates for creating new Wiki notes |

## Maintenance

Before every commit, validation runs automatically via the pre-commit hook:
```bash
python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint
```
