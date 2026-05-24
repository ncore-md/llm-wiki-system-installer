# Workflow Examples

Related: [[Schema/frontmatter-schema.md]], [[AGENTS.md]]

## Ingest

1. Capture source material into `Raw/Sources/`.
2. Run `python3 scripts/wiki_tool.py source-delta`.
3. Read only actionable Raw sources.
4. Update or create compact Wiki notes.
5. Preserve topics and sources traceability.
6. Run `python3 scripts/wiki_tool.py build`.
7. Run `python3 scripts/wiki_tool.py lint`.
8. Refresh the manifest with `python3 scripts/wiki_tool.py source-scan --update --accept-covered`.
9. Append `Wiki/log.md`.

## Query

1. Start with `Wiki/index.md`.
2. Use `python3 scripts/wiki_tool.py search-catalog --query "..."`.
3. Open only the relevant compiled pages.
4. Answer from the Wiki and preserve source links.

## Maintain

1. Run `source-delta`.
2. If there is no actionable delta, do not edit files.
3. Process changed Raw sources.
4. Rebuild, lint, update source manifest, and log.
