
# Ingest Pipeline — Complete Write Path

**Steps 0–9 with mandatory checklist, vault selection logic, and image processing via VL subagent.**

---

## Prerequisites & Pre-flight Check

Before any ingest operation:

1. **Check config:** `python3 scripts/wiki_shared.py vaults 2>&1`
   - If output lists vaults → proceed to Vault Selection
   - If empty or "No project config" → offer setup: spawn subagent with `llm-wiki-setup` skill

2. **Vault Selection:**
   - Check invocation arguments for vault name(s) first (space-separated, `all` = every declared vault)
   - Single-vault shortcut: if pre-flight returns exactly one vault, skip selection and use it directly
   - Validate every chosen vault is declared in config. Wrong names stop the operation.

3. **Permission Check:** If `permissions` does not include `"ingest"` or `"write"`, skip Steps 1–9. Report: "Vault '<name>' has <permissions> — skipping ingest operations."

4. **Config Discovery:** `python3 scripts/wiki_shared.py config --force` → returns JSON with permissions, raw_paths (absolute), tag_routing, allowed_compiled_tags, paths. The `--force` flag guarantees fresh values.

5. **Load Vault Rules:** `python3 -c "from wiki_shared import parse_rules; rules = parse_rules('.'); print(json.dumps(rules, indent=2))"` → max_topics, required_sections, allowed_tags, topics_required_for, tag_routing, source_tag. Fallback: max_topics=5, required_sections=[## Related, ## Sources], allowed_tags=[topic, concept, entity, project].

---

## Mandatory Checklist — Execute Before Proceeding to Next Step

**Do not skip any item. Each check prevents a known failure mode.** Run `grep` commands on files you just wrote — do not trust that a write "looked right."

| # | Check | Command / Action |
|---|-------|------------------|
| **C1** | Read config for ALL paths before writing anything | `wiki_shared.py config --force` — store values in variables (RAW_PATH, WIKI_FOLDER) |
| **C2** | Pre-write YAML verification — confirm frontmatter has real values before calling write tool | Visually inspect: `sources:` must have entries (quoted wikilinks), `topics:` ≥1 plain text topic title; `tags:` must be array |
| **C3** | Post-write re-read — verify file has both frontmatter AND body content after every write |
| **C11** | Source body integrity — verify cleaned source preserved full content (not truncated) | Compare line count before/after cleaning. If body dropped >50% of original lines, RE-DO with in-context editing (no script). |
| **C0 + C11** | Combined read-back — after cleaning, verify BOTH: (a) no timestamp/promo/image patterns remain (`grep '\*\*[0-9]' file` must return 0), AND (b) line count preserved within tolerance | Read first and last 50 lines of the cleaned file. Confirm content flows naturally with no artifacts. |
| **C4** | Sources hard gate — block if any note has empty `sources:` array | `grep -r 'sources: \[\]' <WIKI_FOLDER>/ — if any output, FIX immediately before proceeding |
| **C5** | Array format verification — block if any multi-value field uses scalar form | `grep -A2 'sources:' <WIKI_FOLDER>/*md — must show block-array format, not scalar |
| **C6** | Topics required — concept/entity notes must have ≥1 plain text topic title (NOT wikilinks in YAML frontmatter — Obsidian renders `- [[wikilink]]` as triple brackets). Use raw title text only. | `grep -A2 'topics:' <WIKI_FOLDER>/*md — must have at least one plain text entry |
| **C8** | Required sections — every compiled note must have `## Related` AND `## Sources` in body | `grep -c '^## Related\|^## Sources' <WIKI_FOLDER>/<Note Name>.md — must return count of required sections |
| **C9** | On-disk filename match — verify frontmatter source paths match actual filenames on disk (especially for apostrophes, curly quotes) | `ls <RAW_PATH>/ \| grep <keyword>` — compare against frontmatter. See Unicode normalization below. |
| **C0** | Read-back source body — after cleaning, explicitly read back the cleaned file and verify NO timestamp patterns (`**X:XX** ·`, `HH:MM:SS - Title`), promo lines, or image embeds remain | Read first 50 and last 50 lines of the cleaned source file. If any timestamp/promo pattern found, clean again before proceeding to Step 2 |
| **C10** | Pre-commit lint — run `lint` + `source-lint` explicitly before asking user to commit | `wiki_tool.py lint && wiki_tool.py source-lint` |

**Hard rule:** If C0 triggers (timestamp/promo patterns remain) or C4 triggers (empty sources), do NOT proceed to Step 2. Fix immediately, re-verify, then continue.

---

## Unicode Normalization (Critical)

Both the `obsidian` CLI and native tools (`obsidian_write`, `obsidian_append`) may produce filenames with different Unicode characters than what you type.

1. **CLI filename normalization:** The CLI may normalize curly apostrophes (`′` U+2019 vs straight `'`) or other Unicode characters. After Step 1, **verify the actual on-disk filename** before using it in frontmatter references:
   ```bash
   ls $(python3 scripts/wiki_shared.py config --force 2>/dev/null \| python3 -c "import sys,json; print(json.load(sys.stdin)['raw_paths'][0])") \| grep <keyword>
   ```

2. **YAML quote escaping:** Historical issue — `obsidian_write` previously escaped straight quotes in YAML frontmatter (`\"We're summoning ghosts...`) instead of the curly quotes that appear in actual filenames. **Now resolved** — current versions no longer produce escaped quotes in frontmatter.

3. **Always verify after writing:** After any `obsidian_write` that includes a source path with special characters, check the written frontmatter to confirm it matches on-disk:
   ```bash
   grep -A1 'sources:' $WIKI_FOLDER/<Note Name>.md \| head -5
   ```

---

## Step 0 — Check for Pending Sources

**Action:** Before asking the user for a source, discover vault config and check each validated vault's raw paths for files that need processing.

### Markdown Sources
```bash
cd <wiki-root> && python3 scripts/wiki_tool.py source-scan --update
```
The `--update` flag is **required** — it syncs the manifest with actual files on disk. Without it, `source-scan` only reports entries already in the manifest and will miss new markdown files added since last commit.

### Image Sources
Scan for image files that `source-scan` does not track (SVG, PNG, JPG, WEBP):
```bash
for dir in $RAW_PATHS; do find "$dir" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.webp' -o -name '*.svg' \) 2>/dev/null; done
```

Cross-reference against the catalog to determine if they've already been processed (check `catalog.jsonl` for source references).

### Vision Capability Discovery
```bash
python3 scripts/wiki_shared.py discover [--force]
```
Returns JSON: `{provider, model_id, base_url}` or all null/empty. Results cached in `Schema/.llm-wiki-cache.json`. The cache checks `defaults.agent_has_vision` and `vl_discovery.provider/model_id/base_url`.

To set defaults:
```bash
python3 scripts/wiki_shared.py set-default vl_provider omlx
python3 scripts/wiki_shared.py set-default text_model_id "qwen3.6-35b-a3b-oQ6"
```

To resolve which model to use for a task:
```bash
python3 scripts/wiki_shared.py models image_ingest   # returns {provider, model_id}
```

### Source Validation (Step 0)
- **Image files:** Analyze via subagent with `llm-wiki-vl` skill (see Image Processing below). Continue to Steps 2–9 as normal.
- **Markdown files:** Read the full file first. Verify it follows `_templates/source-note.md`: proper frontmatter with `Title`, `Reference` (URL), `ContentType: [video|article|markdown|pdf]`, `Created` (YYYY-MM-DD), and `tags: [source]`. If ContentType is missing or invalid, fix it before proceeding.
- **Other files:** Skip unless clearly a usable content source.

### Image Processing (via VL Subagent)
Each unprocessed image must be analyzed and converted into wiki notes.

**Pre-step: Collect existing topic titles and real image filenames:**
```bash
python3 << 'PYEOF'
import json, os, glob

wiki_dir = __WIKI_DIR__  # e.g., "Wiki" from config paths.wiki_dir
raw_paths = __RAW_PATHS__  # absolute paths from config (e.g., ["/path/to/Raw/Sources"])
catalog_path = os.path.join(wiki_dir, "catalog.jsonl")

# Find all image files on disk (recursive via **) in each raw path
glob_patterns = []
for rp in raw_paths:
    glob_patterns.extend([os.path.join(rp, "**", f"*.{ext}") for ext in ["png", "jpg", "jpeg", "webp", "svg"]])
image_files = []
for pattern in glob_patterns:
    image_files.extend(glob.glob(pattern, recursive=True))

# Read all wiki notes and collect their source references
referenced = set()
with open(catalog_path) as f:
    for line in f:
        note = json.loads(line)
        sources = note.get("sources", [])
        if isinstance(sources, list):
            for src in sources:
                clean_src = src.strip().strip('"').lstrip('[').rstrip(']').replace('[', '').replace(']', '')
                referenced.add(os.path.basename(clean_src))

# Determine unprocessed images (on disk but not referenced by any wiki note)
unprocessed = []
for img in sorted(image_files):
    basename = os.path.basename(img)
    if basename not in referenced:
        unprocessed.append(basename)

print(f"Total image files on disk: {len(image_files)}")
if unprocessed:
    print(f"Unprocessed (not yet ingested): {len(unprocessed)}")
    for u in unprocessed: print(f"  UNPROCESSED: {u}")
else:
    print("All images have been processed (referenced by wiki notes).")
PYEOF
```

**Resolve the VL model from project config:**
```bash
python3 << 'PYEOF'
import sys, os
sys.path.insert(0, os.getcwd())
os.chdir("<wiki-root>")
from scripts.wiki_shared import resolve_model
model_info = resolve_model("image_ingest")
print(f"{model_info.get('provider')}/{model_info.get('model_id')}")  # e.g., omlx/qwen3.6-...
PYEOF
```

**Spawn the subagent:**
```python
subagent({
  agent: "worker",
  task: "Analyze the image at <image_path> and produce clean wiki notes in Obsidian markdown.\n"
        "EXISTING TOPICS:\n" + open("/tmp/existing_topics.txt").read() + "\n"
        "REAL IMAGE FILES:\n" + open("/tmp/real_image_files.txt").read() + "\n"
        "Follow the llm-wiki-vl skill for output format and rules.",
  model: "<omlx_vl_model_id>",
  skill: "llm-wiki-vl",
  output: "$VL_OUTPUT_FILE"
})
```

**Key details:**
- **Delegation is optional.** If you can read images yourself, do so directly. Otherwise spawn a subagent with `llm-wiki-vl` skill — the child reads images via its own `read` tool and writes notes as output.
- **Multi-note extraction:** If the image contains multiple distinct concepts, tools, or features, produce separate notes for each. Use `---NOTE_BOUNDARY---` to separate them.
- **Model warm-reuse (subagent path only):** The cache flag `defaults.agent_has_vision: True` plus the task override for `image_ingest` keep the ~20GB VL model loaded between subagent calls. After one initial cold start (60–90s), subsequent calls reuse the warm model (~10–20s).
- **Cold-start warning:** The subagent's VL model load takes ~60–90s (cold start on local engine). The subagent itself may take 30–120s more for inference + note generation. Use `async: true` if you want to continue other work while waiting.
- **Verbose output handling:** If the subagent's output contains verbose reasoning or preamble text instead of clean `---NOTE_BOUNDARY---` separated notes, extract the note drafts from within or rewrite them manually.

5. **Create notes from analysis:** Parse `$VL_OUTPUT_FILE` (split on `---NOTE_BOUNDARY---`). For each note: use the `obsidian_write` tool with `note="$WIKI_FOLDER/<Note Name>.md"`, `content="<full note text>"` (including YAML frontmatter), and `vault="<vault-name>"`.

**No VL model found:** If discovery returns no provider/model_id and you do not have VL capabilities yourself, inform the user. Do NOT continue silently with markdown sources only without mentioning it — if you are analyzing images directly (not via subagent), this warm-reuse does not apply.

**Multi-vault note:** When multiple vaults are selected, each is an independent repo. Steps 0–9 run completely for the first vault before moving to the next — no shared state, no cross-vault references. If Step 1 involves a new source (URL/file) provided by the user, that same cleaned content is written to each vault's first configured raw path.

---

## Step 1 — Clean & Store Raw Source (Markdown Only)

**⚠️ CORE PRINCIPLE: Sources are source-faithful. Do NOT summarize, distill, or editorialize.**
Source files preserve ALL factual content from the original. They are NOT summaries, key-point lists, or distilled notes — that's what compiled Wiki notes (Steps 2–9) are for. Source cleaning is about removing noise, not content.

### Deterministic Transforms (Scripts ALLOWED)
Bulk, pattern-based operations on known formats are safe and encouraged for large files:
- Remove timestamps: `**0:08** ·`, chapter markers (`01:10 Title`)
- Remove `[music]`, `[snorts]` filler markers
- Strip promo lines: "Subscribe", "Link in description", Kickstarter/Discord/Steam links
- Normalize frontmatter keys: lowercase → TitleCase (`title` → `Title`, `source` → `Reference`)
- Convert YAML format: scalar arrays to block-array (`tags: [source]` → `tags:\n  - source`)

### Editorial Decisions (In-Context ONLY)
Content judgment must be done in your context using `obsidian_write`:
- Removing navigational clutter (sidebar links, footer text)
- Deciding whether a line is promotional vs. substantive
- Handling ambiguous cases not covered by patterns

### ⚠️ RULES
- **Never write a one-off script for editorial cleaning.** Scripts are only safe for deterministic, pattern-based transforms. Writing scripts that make content decisions risks losing substantive material and adding hidden state.
- **Always read the full file before editing.** Never use line-index slicing (e.g., `lines[13:]`) without first verifying the file structure. Frontmatter boundaries vary by source — always find `---` delimiters programmatically or visually before assuming positions.
- **NO TRUNCATION:** Scripts must never truncate body content. Remove only deterministic noise (timestamps, promo lines). All factual/structural content must be preserved 100%. For large files (>5,000 chars), use in-context editing with `obsidian_write` instead of scripts.
- **Frontmatter must include:** `Title`, `Author` (optional), `Reference` (URL/path), `ContentType: [video|article|markdown|pdf]`, `Created` (YYYY-MM-DD), and `tags: [source]`. Match the `_templates/source-note.md` schema exactly. The `topics` field is NOT used in source notes — it belongs to compiled wiki notes.

### Write & Verify
```bash
obsidian_write note="$RAW_PATH/<cleaned-filename>.md" content="<full markdown with frontmatter>" vault="<vault-name>"
```

**Post-write verification:** After writing a source file, verify the on-disk filename matches what you expect (especially for sources with apostrophes, curly quotes, or em dashes):
```bash
ls $(python3 scripts/wiki_shared.py config --force 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['raw_paths'][0])") | grep <keyword>
```

**C0 — Mandatory read-back:** After cleaning, explicitly read the first 50 and last 50 lines of the cleaned source file. Verify NO timestamp patterns (`**X:XX** ·`, `HH:MM:SS - Title`), promo lines, or image embeds remain. If any found, clean again before proceeding to Step 2.

**C11 — Line count check:** Compare line counts before/after cleaning. If body dropped >50% of original lines, RE-DO with in-context editing (no script).

Continue to Steps 2–9 as normal. Image files bypass cleaning entirely and go from VL analysis (Step 0) directly to Steps 2–9.

---

## Step 2 — Search the Catalog for Related Topics

**Action:** Query the structured wiki catalog (not Obsidian search) to find existing notes on related topics.

```bash
python3 scripts/wiki_tool.py search-catalog --query "key topic"
```

This searches `catalog.jsonl` — a structured index with frontmatter fields (title, tags, topics, sources). Uses word-level matching: any query term triggers a match. Multi-word queries like `"AI agents skills context windows"` return all notes matching any of those terms. Obsidian search alone is insufficient because it only searches note body content.

**If no relevant topics found:** Before creating the note, check if a topic note already exists for this subject area. If not, create one first (write to `Wiki/Topics/<Topic Name>.md` using the topic template), then reference it. Never leave `topics:` empty — every concept/entity must connect to at least one topic note.

---

## Step 3 — Read Relevant Compiled Wiki Notes

**Action:** Use obsidian-cli to read only the most relevant compiled wiki notes from Step 2 results.

```bash
obsidian read path="$WIKI_FOLDER/<Note Name>.md" vault="<vault-name>"
```

Open only the most relevant notes — not all Raw context. Understand what already exists before creating new notes. This lets you:
- Identify if a note should be **updated** (add source references) vs. created new
- Find existing wikilinks to connect into

---

## Step 4 — Create or Update Wiki Notes

**Action:** Use native tools to create focused wiki notes in the correct folder per tag routing.

### MANDATORY: Read template before writing
Every new note MUST start from the corresponding vault template. This ensures consistent frontmatter, required sections (`## Related`, `## Sources`), and proper array formatting.

```bash
cat _templates/<tag>-note.md  # e.g., concept-note.md, entity-note.md
```

### Core Rules (Strictly Enforced)
- **One concept per note.** Extract genuine knowledge — focus on depth, relevance, and completeness per concept rather than filling a template.
- **A single raw source may contain multiple distinct concepts, tools, or architecture decisions — create one separate note per concept.** Do not summarize everything into a single shallow document.
- **Every note must have proper frontmatter** with `tags`, `topics` (wikilinks to relevant topic notes), `sources` array, and `source_count`.
- **The `topics` field MUST contain at least 1 wikilink to an existing topic note.** If no relevant topics found, create a new topic note first (write to `Wiki/Topics/<Topic Name>.md`), then reference it. Never leave empty.
- **Every note must include `## Related` and `## Sources` sections** in the body.
- **Topics must be genuinely relevant.** Each wikilink should represent a subject area the note actually covers — not generic system names.

### Pre-write Verification Checklist
1. **Read template** — `cat _templates/<tag>-note.md`. Verify the template has frontmatter, `## Related`, and `## Sources` sections. Use this as your base structure.
2. **Analyze for distinct knowledge items** — does this source cover multiple concepts, tools, or decisions? Create separate notes if needed.
3. **Populate `topics:`** — use Step 2 catalog results to pick specific, relevant topic titles. Use the **exact title text** from the target note's frontmatter `title:` field — NOT wikilinks. Obsidian renders `- [[wikilink]]` in YAML frontmatter as triple brackets (broken display). Use raw plain text only, e.g., `- Voxel Game Development`. If no relevant topics found, create one first (write to `Wiki/Topics/<Topic Name>.md` using the template), then reference it. Never leave empty.
4. **Replace ALL frontmatter placeholders** — every YAML array field (`sources: []`, `topics: []`) must be filled with real values **BEFORE calling obsidian_write**. The content string's YAML frontmatter is what gets written as note properties — body text sections (`## Sources:`) are NOT parsed as frontmatter. **This is the #1 cause of ingest failures.**
5. Replace all `{{Placeholders}}` with real content — remove template scaffolding text
6. Both `## Related` and `## Sources` sections present at the end (templates include these)
7. **Topic relevance gate:** After writing, verify topics are specific and relevant (not generic system names). If >max_topics from checklist, trim to most relevant.

### ⚠️ CRITICAL — obsidian_write Parsing Behavior
The `obsidian_write` tool reads ONLY the YAML frontmatter block (between `---` delimiters) to set note properties. Body text sections like `## Sources:` are completely ignored for property assignment. If you write:

```yaml
sources: []          # ← THIS IS WHAT GETS SET AS THE PROPERTY
...
---
## Sources           # ← THIS IS IGNORED FOR PROPERTIES
- [[Raw/Sources/example.md]]
```

The note will have an empty `sources` array regardless of what's in the body. **You must fill `sources:` with actual paths inside the YAML frontmatter block before calling obsidian_write.**

### Pre-write Verification (Visual)
Before calling `obsidian_write`, visually confirm the YAML frontmatter contains:
```yaml
sources:
  - "[[Raw/Sources/actual-file.md]]"    ← wikilink format, NOT empty []
topics:
  - <topic-wikilink-from-step-2>        ← specific, relevant topic (plain text)
tags:
  - concept                              ← block array format, NOT scalar
source_count: 1                          ← matches sources array length
```

### Post-write Verification (Programmatic)
After creating notes, verify correctness:

1. **Array format** — ensure `tags`, `topics`, and `sources` use block-array syntax (not scalar):
   ```bash
   grep -A2 'sources:' $WIKI_FOLDER/<Note Name>.md | head -5
   # Should show: sources:\n- "[[Raw/...]]", not: sources: Raw/...
   ```

2. **Topics required** — compiled notes must have at least 1 topic:
   ```bash
   grep -A2 'topics:' $WIKI_FOLDER/<Note Name>.md | head -5
   # Must show at least one entry under topics:, not just: topics:\n```

3. **Source paths and empty arrays — HARD GATE:**
   ```bash
   grep 'sources: \[\]' $WIKI_FOLDER/<Note Name>.md
   # ❌ If this returns anything, the note has an empty sources array — FIX BEFORE PROCEEDING
   ```
   **If `sources: []` is found, do NOT proceed to Step 5 or beyond.** Fix immediately.

### To Update an Existing Note
Use `obsidian read path="..." vault="<vault-name>"` to get current content. Append new body sections with `obsidian_append`. For frontmatter updates — including single-value fields like `source_count` and list properties like `sources` — use the `obsidian_write` tool with full note content (read → modify frontmatter in YAML → write back). The `obsidian property:set` command does not support append semantics for list-type properties (it replaces the entire list), making it unreliable.

---

## Step 5 — Source Links (Integrated into Steps 1 & 4)
Source links are added as part of note creation/updates. The `sources` array in frontmatter contains wikilinks to Raw sources, and `source_count` must equal the number of entries.

---

## Step 6 — Validate with Wiki Tool (Quality Gate)

**Action:** Run build, lint, and source-lint to enforce the wiki's schema contract.

```bash
python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint
```

- **build** — Rebuilds `catalog.jsonl`, `index.md`, and per-folder indexes from all wiki notes. Also auto-fixes empty `sources:` arrays by populating them from body text under `## Sources:` — this is a **safety net, not a substitute** for proper frontmatter. Always fill sources in YAML before writing.
- **lint** — Validates compiled note frontmatter: tag validity, dates (YYYY-MM-DD), source paths resolve on disk (`source_count` matches array length), required sections present (both `## Related` AND `## Sources` — missing either fails the check), topics consistency (concept/entity must have ≥1 topic, ≤max_topics from checklist).
- **source-lint** — Validates raw source frontmatter (title, reference/source present, created date format) and coverage state (processed sources must have `covered_by` entries).

If ANY check fails, fix the issues and repeat. This is your quality gate — Python scripts enforce rules Obsidian doesn't know about (source resolution, schema compliance). **Do NOT skip `source-lint`** — it catches issues that lint doesn't (raw source frontmatter, coverage state).

---

## Step 7 — Update Source Manifest

**Action:** Scan raw sources and update the manifest with coverage state.

```bash
python3 scripts/wiki_tool.py source-scan --update --accept-covered
```

This tracks which raw sources have been processed and how many wiki notes they produced. **Important:** `--accept-covered` validates that all wiki notes in `covered_by` still exist on disk and automatically removes stale entries. Sources with no valid coverage are marked unprocessed.

**Note:** Image files processed in Step 0 are not tracked by this manifest (they have no frontmatter and were never stored as markdown in the configured raw paths). Notes created from images may reference the image file path in their `sources` array if relevant, but these will not appear in source-scan output.

---

## Step 8 — Log the Change

**Action:** Use `wiki_tool.py log` to append a timestamped entry if the ingest meaningfully changed the Wiki (new notes created, existing notes updated).

```bash
python3 scripts/wiki_tool.py log --title "<short title>" --details "<what was affected and why>"
```

Only log if meaningful changes were made — not for every minor update. The entry should describe what files were affected and why.

---

## Step 9 — Commit (Git)

**Action:** Use git to commit all changes. The pre-commit hook automatically runs `doctor + build + lint` as a final safety gate.

```bash
git add -A && git commit -m "<message>"
```

Git is outside Obsidian's scope — obsidian-cli can't touch it. The pre-commit hook provides the last line of defense before changes land in history.

## Step 10 — Security Audit (Public Repos Only)

**Action:** Before pushing to a public repository, run the security audit.

```bash
python3 scripts/wiki_tool.py security-scan --mode public  # Fast secrets check
python3 scripts/wiki_tool.py audit --mode public           # Full compliance scan
```

This is **not part of the ingest pipeline** itself — it's a post-ingest, pre-push operation for public repositories. The audit checks:
- Secrets in tracked files (API keys, tokens, private keys)
- Broken wikilinks across all notes
- Orphaned wiki notes (no incoming backlinks, empty body)
- Source coverage gaps in the manifest

For private repositories, use `--mode private` to skip local path detection.

---

> **See also:**
> - [[system-overview]] — High-level architecture, directory layout, design principles
> - [[entity-hierarchy-data-flow]] — Entity hierarchy, tag routing, frontmatter contract
> - [[shared-infrastructure]] — wiki_tool.py commands in detail (build, lint, source-scan)
> - [[query-maintenance]] — Query read path, maintenance and lint workflows
