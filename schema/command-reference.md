# Command Reference

All commands for `scripts/wiki_tool.py`. Uses only the Python standard library.

Related: [[AGENTS.md]]

## Health & Validation

| Command | Description |
|---------|-------------|
| `python3 scripts/wiki_tool.py doctor` | Non-mutating health check for folders, Python version, catalog, manifest. |
| `python3 scripts/wiki_tool.py lint` | Validates compiled Wiki note frontmatter, allowed tags, source links, `source_count`. |
| `python3 scripts/wiki_tool.py source-lint` | Validates Raw source frontmatter and coverage state (processed sources must have Wiki coverage). |
| `python3 scripts/wiki_tool.py source-delta` | Shows Raw sources not in manifest and vice versa — identifies actionable delta for ingest. |
| `python3 scripts/audit_public.py` | Fails on secrets, local paths, private keys, plugin/cache state. For pre-push checks.

## Indexing & Catalog

| Command | Description |
|---------|-------------|
| `python3 scripts/wiki_tool.py build` | Generates `Wiki/catalog.jsonl`, `Wiki/index.md`, and per-folder index files. Run after any note changes. |

## Source Management

| Command | Description |
|---------|-------------|
| `python3 scripts/wiki_tool.py source-scan` | Lists Raw sources with their processed/covered status. No mutations. |
| `python3 scripts/wiki_tool.py source-scan --update` | Updates manifest entries for all discovered Raw sources. Creates new entries as needed. |
| `python3 scripts/wiki_tool.py source-scan --update --accept-covered` | Updates manifest and marks sources as processed when Wiki notes cover them. Validates that all wiki notes in `covered_by` still exist on disk (removes stale entries automatically). Use after ingest. |

## Search & Query

| Command | Description |
|---------|-------------|
| `python3 scripts/wiki_tool.py search-catalog --query "text"` | Searches compiled Wiki notes through `catalog.jsonl`. Matches against title, topics, and sources fields. |

## Logging

| Command | Description |
|---------|-------------|
| `python3 scripts/wiki_tool.py log --title "t" --details "d"` | Appends a short entry to `Wiki/Logs/log.md`. Creates the log file if it doesn't exist. |

## Typical Workflow Commands

```bash
# After ingesting a new source:
python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-scan --update --accept-covered
# (validates that all wiki notes in covered_by still exist on disk, removes stale entries)

# Pre-commit check:
python3 scripts/wiki_tool.py doctor && python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint

# Before pushing to a public repo:
python3 scripts/audit_public.py
```
