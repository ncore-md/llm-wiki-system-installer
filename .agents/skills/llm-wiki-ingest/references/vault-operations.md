## Vault Operations
All file reads and writes to the Obsidian vault use tools that connect via Chrome DevTools Protocol (CDP). **Never use raw filesystem I/O** (the `write` tool) on vault files — this risks YAML corruption, broken wikilinks, and encoding issues.

For **reading**, searching, properties, and metadata operations: use the `obsidian` CLI.
For **content creation** (notes with frontmatter, large markdown bodies): use the native `obsidian_write` / `obsidian_append` tools. These pass content as structured parameters — no shell escaping needed, handles large YAML frontmatter cleanly.

| Operation | Method |
|-----------|--------|
| Read a note | `obsidian read path="<path>" vault="<vault-name>` |
| Create/overwrite a note | `obsidian_write` tool (preferred for content with frontmatter) |
| Append to a note | `obsidian_append` tool (preferred for structured appends) |
| Search notes | `obsidian search query="<query>" limit=20 vault="<vault-name>` |
| Read a property | `obsidian property:read name=<prop> path="<path>" vault="<vault-name>` |
| Set a property | `obsidian property:set name=<prop> value=<val> type=text\|number\|list\|checkbox path="<path>" vault="<vault-name>` |

**Obsidian timeout:** If an `obsidian` CLI command times out (30s default), check that Obsidian is running and responsive. The CLI connects via Chrome DevTools Protocol — if the browser tab with Obsidian is in a background window or has gone idle, responses can be slow. Retry the command; if it persists, reload Obsidian's plugins (`/reload-plugins` in the command palette).

**Native tools vs CLI for content:** When creating notes with YAML frontmatter, use `obsidian_write` (full replacement) or `obsidian_append` (append content). These tools pass the full note text as a structured parameter — no shell escaping, no env var hacks needed. Native tools are the recommended approach for any note with frontmatter.

**Script discipline:** Only write scripts that are documented in this skill (source-scan, catalog search, VL discovery/processing, shared utilities). Do NOT write one-off scripts for content cleaning, text transformation, or note manipulation — these should be done in your context using `obsidian_write` / `obsidian_append`. One-off scripts risk corrupting frontmatter, losing fields (like `source` URLs), and creating hidden state that breaks downstream steps. If you find yourself about to write a script, ask: "Can I do this by reading the file, processing in context, and writing back with a native tool?" The answer is almost always yes.

**Shell escaping (CLI only):** When using the `obsidian` CLI for filename values that contain spaces, parentheses, or apostrophes (e.g., `So You Don't Have To.md`, `Karpathy's Skills...md`), **always use environment variables**:

```bash
FILENAME=$(echo "Karpathy's Skills just changed Everything (Claude Code).md")
obsidian create path="$RAW_PATH/$FILENAME.md" vault=<vault-name>
Replace `$RAW_PATH` with the first writable path from config `raw_paths`.
```

This is the safest approach — no inline escaping needed. Inline shell escaping (single quotes with `\''` for apostrophes) is a fallback only when env vars are impractical. For note content, prefer `obsidian_write` / `obsidian_append` tools which accept structured parameters.

**Unicode normalization:** Both the `obsidian` CLI and native tools (`obsidian_write`, `obsidian_append`) may produce filenames with different Unicode characters than what you type. Two known issues:

1. **CLI filename normalization:** The CLI may normalize curly apostrophes (`′` U+2019 vs straight `'`) or other Unicode characters. After Step 1, **verify the actual on-disk filename** before using it in frontmatter references:

   ```bash
   ls $(python3 scripts/wiki_shared.py config --force 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['raw_paths'][0])") | grep <keyword>
   ```
or use the first `raw_path` from config discovery.

2. **YAML quote escaping:** Historical issue — `obsidian_write` previously escaped straight quotes in YAML frontmatter (e.g., writing `\"We're summoning ghosts...` instead of the curly quotes that appear in actual filenames). This caused lint failures because source paths wouldn't match on-disk files. **Now resolved** — current versions of `obsidian_write` no longer produce escaped quotes in frontmatter.

**Always verify frontmatter after writing:** After any `obsidian_write` that includes a source path with special characters (apostrophes, curly quotes, em dashes), check the written frontmatter to confirm it matches the on-disk filename:

```bash
grep -A1 'sources:' $WIKI_FOLDER/<Note Name>.md | head -5
```
Replace `$WIKI_FOLDER` with the folder from config's `tag_routing`.

If you ever see escaped quotes (`\"`) that don't match the on-disk filename, fix them before running lint. Use either:

- **`edit` tool** — matches the exact escaped text and replaces with correct unicode characters (handles bytes natively)
- **Python one-liner** — read file, do byte-accurate `.replace()`, write back

A mismatch causes lint failures — the wiki tool does exact string matching on source paths.
