## Sources
- [[Raw/Sources/example.md]]  ← THIS IS IGNORED FOR PROPERTIES
```

The note will have an empty `sources` array regardless of what's in the body. **You must fill `sources:` with actual paths inside the YAML frontmatter block before calling obsidian_write.** The body text `## Sources` section is for display only — it does NOT populate the frontmatter property.

**Pre-write verification:** Before calling `obsidian_write`, visually confirm the YAML frontmatter contains:
```yaml
sources:
  - "[[Raw/Sources/actual-file.md]]"    ← wikilink format, NOT empty []
topics:
  - <topic-wikilink-from-step-2>        ← specific, relevant topic
tags:
  - concept                              ← not scalar
source_count: 1                          ← matches array length
```

**YAML frontmatter format — array syntax required:**
All multi-value fields MUST use YAML block-array format, never scalar or inline form. This is enforced by `lint` and required for the custom YAML parser in `wiki_tool.py` to read them correctly.

```yaml
# ✅ Correct — block array format
tags:
  - concept
topics:
  - <topic-wikilink-from-step-2>
sources:
  - "[[Raw/Sources/actual-file.md]]"
source_count: 1

# ❌ Wrong — scalar form (causes lint failures)
tags: concept
topics: <scalar-value>   # scalar — lint expects array
sources: "[[Raw/Sources/example.md]]"  # must be array, not scalar
topics: <value1>,<value2>   # inline comma — breaks parser
```

**Post-write verification:** After creating notes, verify correctness:

1. **Array format** — ensure `tags`, `topics`, and `sources` use block-array syntax (not scalar):

```bash
grep -A2 'sources:' $WIKI_FOLDER/<Note Name>.md | head -5
# Should show: sources:\n- "[[Raw/...]]", not: sources: Raw/...
```
Replace `$WIKI_FOLDER` with the folder from config's `tag_routing`. Sources MUST use wikilink format: `"[[Raw/Sources/file.md]]"`.

2. **Topics required** — compiled notes must have at least 1 topic:
```bash
grep -A2 'topics:' $WIKI_FOLDER/<Note Name>.md | head -5
# Must show at least one entry under topics:, not just:
topics:
```
Replace `$WIKI_FOLDER` with the folder from config's `tag_routing`. If empty, add a topic reference — use Step 2 results. If no topics found, create one first (write to `Wiki/Topics/<Topic Name>.md` using the template), then reference it.

3. **Topic count** — verify topics array has ≥1 and ≤max_topics entries (from parsed rules):
```bash
grep -A2 'topics:' $WIKI_FOLDER/<Note Name>.md | head -5
# Must show at least one entry. Count entries — if >max_topics from AGENTS.md checklist, trim to most relevant.
# Replace `$WIKI_FOLDER` with the folder from config's `tag_routing`.```


4. **Source paths and empty arrays — HARD GATE:** Verify frontmatter YAML has real wikilinks, not placeholders:

```bash
grep -A2 'sources:' $WIKI_FOLDER/<Note Name>.md | head -5
# ✅ Must show: sources:\n  - "[[Raw/Sources/actual-file.md]]"
grep 'sources: \[\]' $WIKI_FOLDER/<Note Name>.md
# ❌ If this returns anything, the note has an empty sources array — FIX BEFORE PROCEEDING
```
Replace `$WIKI_FOLDER` with the folder from config's `tag_routing`. **If `sources: []` is found, do NOT proceed to Step 5 or beyond.** Fix immediately:
- Read the file with `edit` tool
- Replace `sources: []\nsource_count: 0` with the actual source wikilinks and correct count
- Re-read to confirm fix before continuing

This is a **blocking failure** — notes with empty sources will fail lint and corrupt the catalog. Never commit or proceed until all new/updated notes have populated source arrays.

If you ever see escaped quotes (`\"`) in the YAML that don't match the actual filename on disk, fix them before running lint. This was a historical issue with `obsidian_write` (now resolved) — it previously escaped straight quotes in YAML while the filesystem stored curly/apostrophe characters. See **Unicode normalization** above for details.

**To update an existing note:** Use `obsidian read path="..." vault="<vault-name>"` to get current content. Append new body sections with the `obsidian_append` tool (`note="..."`, `content="<new content>"`, `vault="<vault-name>`). For frontmatter updates — including single-value fields like `source_count` and list properties like `sources` — use the `obsidian_write` tool with full note content (read → modify frontmatter in YAML → write back). The `obsidian property:set` command does not support append semantics for list-type properties (it replaces the entire list), making it unreliable for adding sources or topics to existing notes.
