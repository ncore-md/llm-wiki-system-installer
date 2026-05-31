# Detailed Workflow Steps

## Workflow

**Multi-vault note:** When multiple vaults are selected, each is an independent repo. Steps 0–9 run completely for the first vault before moving to the next — no shared state, no cross-vault references. If Step 1 involves a new source (URL/file) provided by the user, that same cleaned content is written to each vault's first configured raw path (from config `raw_paths`).

### Mandatory Checklist — Execute Before Proceeding to Next Step
**Do not skip any item.** Each check prevents a known failure mode. Run `grep` commands on the files you just wrote — do not trust that a write "looked right."

| # | Check | Command / Action |
|---|-------|------------------|
| C1 | **Read config for ALL paths** before writing anything | `python3 scripts/wiki_shared.py config --force` — store values in variables (`RAW_PATH`, `WIKI_FOLDER`, etc.). Config defaults and tag routing are cached in Schema/.llm-wiki-cache.json — auto-invalidated when AGENTS.md changes (file hash comparison). Templates are cached in memory via `wiki_shared.py get_cached_template()` (function-level cache, safe for CLI usage) |
| C2 | **Pre-write YAML verification** — confirm frontmatter has real values before calling write tool | Visually inspect: `sources:` must have entries (quoted wikilinks), `topics:` must have ≥1 plain text topic title; `tags:` must be array |
| C3 | **Post-write re-read** — verify file has both frontmatter AND body content after every write |
| C11 | **Source body integrity** — verify cleaned source preserved full content (not truncated) | Compare line count before/after cleaning. If body dropped >50% of original lines, RE-DO with in-context editing (no script). |
| C0 + C11 | **Combined read-back** — after cleaning, verify BOTH: (a) no timestamp/promo/image patterns remain (`grep '\*\*[0-9]' file` must return 0), AND (b) line count preserved within tolerance | Read first and last 50 lines of the cleaned file. Confirm content flows naturally with no artifacts.
| C4 | **Sources hard gate** — block if any note has empty `sources:` array | `grep -r 'sources: \[\]' <WIKI_FOLDER>/ — if any output, FIX immediately before proceeding |
| C5 | **Array format verification** — block if any multi-value field uses scalar form | `grep -A2 'sources:' <WIKI_FOLDER>/*md — must show block-array format, not scalar |
| C6 | **Topics required** — concept/entity notes must have ≥1 plain text topic title (from parsed rules). NOT wikilinks — Obsidian renders `- [[wikilink]]` in YAML frontmatter as triple brackets. Use raw title text only (e.g., `- Voxel Game Development`). | `grep -A2 'topics:' <WIKI_FOLDER>/*md — must have at least one plain text entry, no [[ ]] brackets |
| C8 | **Required sections** — every compiled note must have `## Related` AND `## Sources` in body | `grep -c '^## Related\|^## Sources' <WIKI_FOLDER>/<Note Name>.md — must return count of required sections |
| C9 | **On-disk filename match** — verify frontmatter source paths match actual filenames on disk (especially for apostrophes, curly quotes) | `ls <RAW_PATH>/ | grep <keyword>` — compare against frontmatter |
| C0 | **Read-back source body** — after cleaning, explicitly read back the cleaned file and verify NO timestamp patterns (`**X:XX** ·`, `HH:MM:SS - Title`), promo lines, or image embeds remain | Read first 50 and last 50 lines of the cleaned source file. If any timestamp/promo pattern found, clean again before proceeding to Step 2 |
| C10 | **Pre-commit validation** — run `build` + `lint` + `source-lint` explicitly before asking user to commit | **Single vault:** `python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint`<br>**Multi-vault:** See Step 6b — use `python3 scripts/wiki_tool_all.py validate-all` for parallel per-vault validation (90s timeout each) |
| C12 | **Cross-reference isolation** — verify all wikilinks in newly written notes resolve within the target vault's wiki_root | `python3 << 'PYEOF'\nimport json, os, glob\nwiki_root = "__WIKI_ROOT__"  # current vault's wiki root from config\nerrors = []\nfor note_file in glob.glob(os.path.join(wiki_root, "Wiki", "**", "*.md"), recursive=True):\n    with open(note_file) as f:\n        content = f.read()\n    import re\n    for match in re.finditer(r'\\[\\[([^\\]]+)\\]\\]', content):\n        link = match.group(1)\n        if '/' in link and not link.startswith('http'):\n            full_path = os.path.join(wiki_root, link)\n            if not os.path.exists(full_path):\n                errors.append(f"{note_file}: broken link [[{link}]]")\nif errors:\n    print("C12 FAIL:")\n    for e in errors[:50]:  # cap output\n        print(f"  {e}")\nelse:\n    print("C12 PASS")\nPYEOF` | **Efficient mode (default):** Run once after all Steps 0–9 complete for the vault. Scan all notes in Wiki/ directory — if any wikilink does not resolve within this vault's wiki_root, FIX before proceeding. **Strict mode (optional):** Run after every individual note write. Enable via `defaults.isolation_mode: "strict"` in config.json (default is `"efficient"`) |

**Hard rule:** If C0 triggers (timestamp/promo patterns remain) or C4 triggers (empty sources), do NOT proceed to Step 2. Fix immediately, re-verify, then continue.

**Image-only markdown detection (`--keep-images` flag):** After source validation, if the `--keep-images` flag was passed to ingest, check each markdown file whose body contains only image embeds (`![](...)`) with no substantive text. Extract the embedded image paths and route them through VL processing (same path as raw images on disk). If `--keep-images` is NOT set, continue with current behavior (image-only sources cleaned normally, may become empty and be skipped/deleted). Default: flag not set (backward compatible).

### Step 0 - Check for Pending Sources
**Action:** Before asking the user for a source, discover vault config and check each validated vault's raw paths for files that need processing.

**Per-Vault Variable Re-Collection:** At the beginning of Step 0 for each vault, explicitly re-collect ALL variables from that vault's settings in the shared project config. Do NOT reuse values from a previous vault.

**Config Discovery:** Before scanning, read the shared project config to get permissions and raw paths for the current vault:
```bash
cd <wiki-root> && python3 scripts/wiki_shared.py config --force 2>&1
```
This returns JSON with `permissions` (e.g., `["read", "write", "ingest"]`) and `raw_paths` (e.g., `["Raw/Source", "Raw/Sources"]`). If the vault has only `"read"` permission, skip all write/ingest operations — report "Vault is read-only (no ingest/write permission)" and move to the next vault.

**Per-vault re-collection (after config discovery, before any other Step 0 action):**
1. **Resolve wiki root:** `cd <wiki-root> && python3 scripts/wiki_shared.py resolve-path "<vault-name>" 2>&1`
   — extract the new vault's `wiki_root` from config, do NOT reuse previous vault's path
2. **Re-collect topic titles** from THIS vault's `catalog.jsonl` (read from its own wiki_root,
   not a previously cached path)
3. **Re-scan raw paths** from THIS vault's config entry (do not reuse previous scan results)

**Hard rule:** If `__WIKI_DIR__` or `__RAW_PATHS__` were populated from a previous vault's settings, they are INVALID for the current vault. Always re-collect after switching vaults.

**Load Vault Rules:** Parse structured rules from AGENTS.md (the `---checklist---` section) to get vault-specific constraints:
```bash
cd <wiki-root> && python3 -c "
import json, sys; sys.path.insert(0, 'scripts')
from wiki_shared import parse_rules
rules = parse_rules('.')  # uses AGENTS.md at current directory
print(json.dumps(rules, indent=2))
"
```
Store the parsed rules in context (max_topics, required_sections, allowed_tags, topics_required_for, tag_routing, source_tag). If parsing fails or AGENTS.md is missing, fall back to defaults: max_topics=5, required_sections=[## Related, ## Sources], allowed_tags=[topic, concept, entity, project].

**Permission Check:** If `permissions` does not include `"ingest"` or `"write"`, skip Steps 1–9 for this vault. Report: "Vault '<name>' has <permissions> — skipping ingest operations." Continue to the next vault.

Run from the wiki root directory:
```bash
cd <wiki-root> && python3 scripts/wiki_tool.py source-scan --update
```

The `--update` flag is **required** here — it syncs the manifest with actual files on disk. Without it, `source-scan` only reports entries already in the manifest and will miss any new markdown files added since last commit.

This lists raw **markdown** sources with their coverage state (new files will appear as unprocessed). Then also scan for image files that `source-scan` does not track (SVG, PNG, JPG, WEBP) — scan **all raw paths from config** including subfolders:
```bash
for dir in $RAW_PATHS; do find "$dir" -type f \( -name '*.png' -o -name '*.jpg' -o -name '*.webp' -o -name '*.svg' \) 2>/dev/null; done
```
Replace `$RAW_PATHS` with space-separated **absolute** paths from config `raw_paths` (e.g., `/path/to/Raw/Sources /path/to/other/raw`).

For image files, cross-reference against the catalog to determine if they've already been processed. Run this check — uses config's `raw_paths` for scanning instead of hardcoded paths:
```bash
python3 << 'PYEOF'
import json, os, glob

wiki_dir = __WIKI_DIR__  # e.g., "Wiki" from config paths.wiki_dir
raw_paths = __RAW_PATHS__  # absolute paths from config (e.g., ["/path/to/Raw/Sources"])
catalog_path = os.path.join(wiki_dir, "catalog.jsonl")

# Find all image files on disk (recursive via **) in each raw path
glob_patterns = []
for rp in raw_paths:
    glob_patterns.extend([
        os.path.join(rp, "**", f"*.{ext}")
        for ext in ["png", "jpg", "jpeg", "webp", "svg"]
    ])
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
                # Strip wikilink brackets (e.g. "[[Raw/Sources/image.png]]") then extract filename
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
    for u in unprocessed:
        print(f"  UNPROCESSED: {u}")
else:
    print("All images have been processed (referenced by wiki notes).")
PYEOF
```

Present the combined results to the user:
- **Has unprocessed sources (markdown or image):** validate each one (see Source Validation below), then process them automatically. Run Steps 1–9 for markdown sources; run image processing (read → analyze → create notes) for images. Do this until all unprocessed sources in that vault are covered, then move to the next selected vault.
- **All processed (raw paths exist but everything covered):** ask if they want to add a new source
- **No raw path exists:** report "Raw folder not found — ingest will not continue for this vault"

After the report, decide whether to ask for a new source:
- **At least one validated vault with configured raw paths but no unprocessed work:** ask the user for a URL, file path, or pasted content to ingest into those vaults
- **No validated vaults with configured raw paths:** do NOT ask for a source — there is nowhere to ingest into. Inform the user and stop.

**Important:** Asking for a new URL/file/source is only valid when at least one validated vault has configured raw paths (from config `raw_paths`). If all selected vaults lack this, there is nothing to ingest into — stop and inform the user.

**Vision Capability Discovery:** Before processing any image files, discover which vision-capable model is available. Run this ONCE per session — results are cached in the shared wiki cache (`Schema/.llm-wiki-cache.json`).

```bash
python3 scripts/wiki_shared.py discover [--force]
```

The `--force` flag re-runs discovery even if cache is fresh. Without it, the shared utility checks `defaults.agent_has_vision` and `vl_discovery.provider/model_id/base_url` — if all are populated, it returns cached results.

**Interpret the discovery result (JSON output):**
- **`provider: "omlx", model_id, base_url populated`** — use the discovered local engine. Read values from cache output.
- **All null/empty** — No VL model found locally. Inform the user that image processing is unavailable and continue with markdown sources only.

To set defaults (so all skills use consistent models):
```bash
python3 scripts/wiki_shared.py set-default vl_provider omlx
python3 scripts/wiki_shared.py set-default text_model_id "qwen3.6-35b-a3b-oQ6"
```
To set per-task overrides:
```bash
python3 scripts/wiki_shared.py set-override image_ingest vl_model_id "qwen3.6-35b-a3b-mlx-vl-oQ4-FP16"
```
To resolve which model to use for a task:
```bash
python3 scripts/wiki_shared.py models image_ingest   # returns {provider, model_id}
python3 scripts/wiki_shared.py models note_generation
```


**Source Validation:** Before processing any unprocessed file, check its type and content:
- **Image files** (`.jpg`, `.png`, `.webp`): Analyze via a subagent with the `llm-wiki-vl` skill (see **Image Processing** below). Continue to Steps 2–9 as normal (use the image path in source references). No frontmatter needed — these are treated as visual sources, not markdown.
- **Markdown files** (`.md`): Read the full file first. Verify it follows `_templates/source-note.md`: proper frontmatter with `Title`, `Reference` (URL), `ContentType: [video|article|markdown|pdf]`, `Created` (YYYY-MM-DD), and `tags: [source]`. Check that:
  - **ContentType:** Must be one of the vault's allowed content types (`video`, `article`, `markdown`, `pdf`). If missing or invalid, fix it before proceeding.
  - **Array format:** Multi-value fields MUST use YAML block-array syntax (`ContentType:\n  - video`), never scalar form.
  - Fields are clean (no promotional URLs or junk in values)
  - The file has substantive body content beyond frontmatter
  Files that fail these checks should be fixed in place (clean the frontmatter, normalize format) before proceeding. Files that are empty or contain only images/embeds without text should be flagged and removed.
- **Other files**: Skip unless clearly a usable content source.

**Image Processing:** Each unprocessed image must be analyzed and converted into wiki notes. Choose the approach that matches your capabilities:

- **If you have VL/image reading capability:** read each image directly with your `read` tool, then write wiki notes using the output format rules below.
- **If you do NOT have VL capability:** spawn a subagent with the `llm-wiki-vl` skill for each image. The child reads images via its own `read` tool and writes notes as output.

**Model warm-reuse (subagent path only):** The cache flag `defaults.agent_has_vision: True` plus the task override for `image_ingest` keep the ~20GB VL model loaded between subagent calls. After one initial cold start (60-90s), subsequent calls reuse the warm model (~10-20s). Spawn each subagent as a separate call — no batching. If you are analyzing images directly, this warm-reuse does not apply.

**VL model health check timing:** Before spawning any VL subagents, call `check_vl_model_health()` (from wiki_shared.py). If the model is unavailable or degraded:
- Skip VL processing entirely and continue with text sources only (inform user)
- Do NOT wait or retry — the health check result is cached for the session

**Hybrid streaming VL processing (multiple images):**
1. Model warm-reuse: `defaults.agent_has_vision: True` + task override keep VL model loaded between calls
2. Spawn first batch of VL subagents with `async: true` (up to concurrency limit, default 4)
3. As each result arrives: process immediately, spawn next queued image to fill open slot
4. Text source processing (Steps 1-9) runs in parallel with VL image processing — independent work streams
5. After all VL outputs are collected, proceed to consolidation step (see below)
6. Consolidation decision document produced → orchestrator writes notes based on consolidation output
7. Continue with Steps 1-9 (text source processing)

**Parallel execution safety rules:** Never write to another vault's wiki_root during parallel processing. Each VL subagent must be given its own `wiki_root` and `raw_paths`. Catalog search results are per-vault; do not mix entries from different vaults. If any parallel operation fails, report failures per-vault and continue with successful ones.

**Multi-note extraction:** If the image contains multiple distinct concepts, tools, or features, produce separate notes for each. Use `---NOTE_BOUNDARY---` to separate them.

**Pre-step: Collect existing topic titles and real image filenames** (so the subagent can populate `topics` with real wikilinks and use correct source paths):
   ```bash
   python3 << 'PYEOF'
   import json, os, glob

   wiki_dir = __WIKI_DIR__  # e.g., "Wiki" from config
   catalog_path = os.path.join(wiki_dir, "catalog.jsonl")
   topic_titles = []
   with open(catalog_path) as f:
       for line in f:
           note = json.loads(line)
           tag_val = note.get("tag", "")
           if isinstance(tag_val, str) and tag_val.strip().lower() == "topic":
               title = note.get("title", "")
               if title:
                   topic_titles.append(title)
           elif isinstance(tag_val, list) and "topic" in tag_val:
               title = note.get("title", "")
               if title:
                   topic_titles.append(title)

   with open("/tmp/existing_topics.txt", "w") as f:
       for t in topic_titles:
           f.write(t + "\n")
   print(f"Found {len(topic_titles)} existing topic notes:")
   for t in topic_titles[:20]:
       print(f"  - {t}")

   # Collect real image filenames (scan all config raw_paths recursively)
   glob_patterns = []
   for rp in __RAW_PATHS__:  # absolute paths from config
       glob_patterns.extend([os.path.join(rp, "**", ext) for ext in ["*.png", "*.jpg", "*.jpeg", "*.webp"]])
   image_files = sorted([os.path.relpath(f, ".") for pattern in glob_patterns for f in glob.glob(pattern, recursive=True)])
   with open("/tmp/real_image_files.txt", "w") as f:
       for img in image_files:
           if not os.path.basename(img).endswith(".svg"):
               f.write(img + "\n")
   print(f"Real image files: {len(image_files)}")
   PYEOF
   ```

**Resolve the VL model from project config (source of truth):**
```bash
python3 << 'PYEOF'
import sys, os
sys.path.insert(0, os.getcwd())
os.chdir("<wiki-root>")  # e.g., /Users/bernardoresende/Core/.llm-wiki/Core
from scripts.wiki_shared import resolve_model
model_info = resolve_model("image_ingest")
provider = model_info.get("provider")
model_id = model_info.get("model_id")
base_url = model_info.get("base_url")
if not provider or not model_id:
    print(f"ERROR: VL model not configured. Set vl_provider and vl_model_id in .llm-wiki-config/config.json.")
    sys.exit(1)
print(f"{provider}/{model_id}")  # e.g., omlx/qwen3.6-35b-a3b-mlx-vl-oQ4-FP16
PYEOF
```

**Spawn the subagent:**
```python
subagent({
  agent: "worker",
  task:
    "Analyze the image at <image_path> and produce clean wiki notes in Obsidian markdown.\n"
    "EXISTING TOPICS:\n" + open("/tmp/existing_topics.txt").read() + "\n"
    "REAL IMAGE FILES:\n" + open("/tmp/real_image_files.txt").read() + "\n"
    "Follow the llm-wiki-vl skill for output format and rules.",
  model: "<omlx_vl_model_id>",      # e.g., omlx/qwen3.6-35b-a3b-mlx-vl-oQ4-FP16
  skill: "llm-wiki-vl",
  output: "$VL_OUTPUT_FILE"
})
```

**Key details:**
- **Delegation is optional.** If you can read images yourself, do so directly. Otherwise spawn a subagent with `llm-wiki-vl` skill — the child reads images via its own `read` tool and writes notes as output.
- The `llm-wiki-vl` skill (injected into the subagent) provides output format rules, tag routing, and frontmatter schema.
- Existing topics are passed as context so the subagent can populate `topics` with real wikilinks.
- Real image filenames are passed so the subagent uses correct paths in `sources` (no hallucination).
- **Keep model warm (subagent path only):** The cache flag `defaults.agent_has_vision: True` plus the task override for `image_ingest` keep the VL model loaded between subagent calls. Each subsequent call reuses the warm model (~10-20s) instead of cold starting (~60-90s). If the model is unloaded (e.g., after a long pause), accept one cold start, then subsequent calls will be fast.

5. **Create notes from analysis:**
- Generate a unique output filename for this session to avoid stale cache contamination: `VL_OUTPUT_FILE="/tmp/vl_wiki_notes_$(date +%s).md"`
- **Subagent path:** Parse `$VL_OUTPUT_FILE` (split on `---NOTE_BOUNDARY---`). For each note: use the `obsidian_write` tool with `note="$WIKI_FOLDER/<Note Name>.md"`, `content="<full note text>"` (including YAML frontmatter), and `vault="<vault-name>"`. Replace `$WIKI_FOLDER` with config's `tag_routing` value. Reference the image file path in source arrays using a path from config's `raw_paths` (e.g., `$RAW_PATH/image-name.png`).
- **Direct path:** You analyzed the image yourself — write each note directly with `obsidian_write` (or `obsidian_append` for updates), using the same frontmatter schema and output format rules.

**No VL model found:** If discovery returns no `provider`/`model_id`, and you do not have VL capabilities yourself, inform the user: "No vision-capable model is available. Image processing will be skipped — markdown sources can still be ingested." Do NOT continue silently.

**Cold-start warning (subagent path only):** The subagent's VL model load takes ~60-90s (cold start on local engine). The subagent itself may take 30–120s more for inference + note generation. Use `async: true` if you want to continue other work while waiting.

**Verbose output handling (subagent path only):** If the subagent's output in `$VL_OUTPUT_FILE` contains verbose reasoning or preamble text instead of clean `---NOTE_BOUNDARY---` separated notes, extract the note drafts from within (they appear as structured markdown blocks with `---YAML---` frontmatter) or rewrite them manually based on the VL analysis. The `llm-wiki-vl` skill enforces clean output but cannot guarantee it for all VL models.

### Consolidation Step (After VL Batch, Before Steps 1-9)
**Action:** Evaluate VL subagent output alongside the orchestrator's source mapping to produce a structured decision document for note creation, update, or merge.

**Position:** This step runs AFTER VL batch completion and BEFORE text source processing (Steps 1-9). The orchestrator evaluates all collected VL outputs, then executes note writes based on the consolidation decision.

**Input:**
- `$VL_OUTPUT_FILE`: Path to VL subagent's output (notes separated by `---NOTE_BOUNDARY---`, each with metadata lines)
- `$SOURCE_MAPPING`: JSON describing source-to-vault relationships (from orchestrator context)

**Process:**
1. Spawn a subagent with the `llm-wiki-consolidate` skill (model: orchestrator's text model, config-driven)
2. Pass to the subagent:
   - `$VL_OUTPUT_FILE` as a file reference (negligible token impact ~800 tokens)
   - `$SOURCE_MAPPING` JSON from orchestrator context
   - Optional: catalog context if needed for R5 (existing topic detection)
3. The consolidate subagent applies rules R1-R8 and produces a JSON decision document at `$CONSOLIDATE_OUTPUT_FILE`
4. Orchestrator reads the decision document and executes writes via `obsidian_write`/`obsidian_append`
5. Orchestrator reviews and resolves any `ambiguous_cases` (R3/R4 cross-topic overlap, R7 low-quality VL output)
6. Continue with Steps 1-9 (text source processing)

**Note:** The consolidate skill does NOT write notes to disk — it produces only the decision document. The orchestrator executes all writes based on this output.

**Metadata Stripping Parser (Orchestrator):** Before passing VL output to consolidate or writing notes, the orchestrator strips metadata lines from each note draft:
- Regex pattern (per-note): `^---(SOURCE_NOTE|IMAGE_INDEX|CONSOLIDATION_CONFIDENCE|CONSOLIDATION_REASON):\s*.+$`
- Strip all matching lines that appear BEFORE each `---NOTE_BOUNDARY---` separator
- Graceful fallback: if a line starts with `---` but doesn't match metadata pattern, keep it (it's part of the note content)
- Missing fields: if SOURCE_NOTE is absent, derive from filename heuristics; if IMAGE_INDEX missing, default to 1/N where N = total notes in batch
- Malformed output: if VL produces verbose reasoning before note drafts, extract structured markdown blocks (look for `---YAML---` frontmatter markers)
- Edge case: metadata lines may contain colons in values (e.g., `SOURCE_NOTE: tutorial-install.md`), regex handles this via greedy capture after first colon

### Step 1 — Clean & Store Raw Source
**Action:** Write cleaned Markdown into the vault's configured raw paths (from config `raw_paths`) using the native tools. Use the first writable path in the list (e.g., `Raw/Sources/`). **Skip this step for image files** — they bypass cleaning entirely and go from VL analysis (Step 0) directly to Steps 2–9.

**⚠️ CORE PRINCIPLE: Sources are source-faithful. Do NOT summarize, distill, or editorialize.**
Source files preserve ALL factual content from the original. They are NOT summaries, key-point lists, or distilled notes — that's what compiled Wiki notes (Steps 2–9) are for. Source cleaning is about removing noise, not content.

**Deterministic transforms (scripts ALLOWED):** Bulk, pattern-based operations on known formats are safe and encouraged for large files:
- Remove timestamps: `**0:08** ·`, chapter markers (`01:10 Title`)
- Remove `[music]`, `[snorts]` filler markers
- Strip promo lines: "Subscribe", "Link in description", Kickstarter/Discord/Steam links
- Normalize frontmatter keys: lowercase → TitleCase (`title` → `Title`, `source` → `Reference`)
- Convert YAML format: scalar arrays to block-array (`tags: [source]` → `tags:\n  - source`)

**Editorial decisions (in-context ONLY):** Content judgment must be done in your context using `obsidian_write`:
- Removing navigational clutter (sidebar links, footer text)
- Deciding whether a line is promotional vs. substantive
- Handling ambiguous cases not covered by patterns

**⚠️ RULE: Never write a one-off script for editorial cleaning.** Scripts are only safe for deterministic, pattern-based transforms. Writing scripts that make content decisions risks losing substantive material and adding hidden state.

**⚠️ CRITICAL: Always read the full file before editing.** Never use line-index slicing (e.g., `lines[13:]`) without first verifying the file structure. Frontmatter boundaries vary by source — always find `---` delimiters programmatically or visually before assuming positions.

**⚠️ Empty-after-clean guard:** Before removing image embeds, check if the file body contains ONLY image embeds and no substantive text. If removing all `![](...)` would leave the file with only frontmatter:
- **If `--keep-images` flag is set:** DO NOT remove embeds. Skip cleaning and route to VL processing.
- **If `--keep-images` is NOT set:** Skip this source entirely and log "skipped (image-only, --keep-images not set)". Do NOT delete the file.

**What to remove (deterministic):** timestamps (`**0:08** ·`, `01:10 Chapter`), `[music]`/`[snorts]` markers, promo lines (subscribe prompts, Kickstarter/Discord/Steam links, "link in description"), image embeds (`![](...)`).
**What to keep (source-faithful): ALL factual content.** Quotes, data points, technical explanations, paper names/authors/institutions/dates, quantitative results (accuracy numbers, benchmarks), core arguments and conclusions. Preserve every fact from the original.
**⚠️ NO TRUNCATION:** Scripts must never truncate body content. Remove only deterministic noise (timestamps, promo lines). All factual/structural content must be preserved 100%. For large files (>5,000 chars), use in-context editing with `obsidian_write` instead of scripts.
**Frontmatter must include:** `Title`, `Author` (optional), `Reference` (URL/path), `ContentType: [video|article|markdown|pdf]`, `Created` (YYYY-MM-DD), and `tags: [source]`. Match the `_templates/source-note.md` schema exactly. The `topics` field is NOT used in source notes — it belongs to compiled wiki notes.

Use `obsidian_write` tool:
```
obsidian_write note="$RAW_PATH/<cleaned-filename>.md" content="<full markdown with frontmatter>" vault="<vault-name>"
Replace `$RAW_PATH` with the first writable path from config `raw_paths` (e.g., `Raw/Sources`).
```

Or via CLI (requires inline content expansion — prefer native tools):
```bash
obsidian create path="$RAW_PATH/<cleaned-filename>.md" vault=<vault-name> overwrite content="$CONTENT"
Replace `$RAW_PATH` with the first writable path from config `raw_paths`.
```

**Post-write verification:** After writing a source file, verify the on-disk filename matches what you expect (especially for sources with apostrophes, curly quotes, or em dashes):

```bash
ls $(python3 scripts/wiki_shared.py config --force 2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin)['raw_paths'][0])") | grep <keyword>
```
or use the first `raw_path` from config discovery. If the CLI normalized characters (e.g., curly apostrophe → straight), use the **actual on-disk name** in all subsequent frontmatter references. See **Unicode normalization** above for details.

**C0 — Mandatory read-back:** After cleaning, explicitly read the first 50 and last 50 lines of the cleaned source file. Verify NO timestamp patterns (`**X:XX** ·`, `HH:MM:SS - Title`), promo lines, or image embeds remain. If any found, clean again before proceeding to Step 2.

**C11 — Line count check:** Compare line counts before/after cleaning. If body dropped >50% of original lines, RE-DO with in-context editing (no script).

Continue to Steps 2–9 as normal.

### Step 2 — Search the Catalog for Related Topics
**Action:** Query the structured wiki catalog (not Obsidian search) to find existing notes on related topics.

```bash
python3 scripts/wiki_tool.py search-catalog --query "key topic"
```

This searches `catalog.jsonl` — a structured index with frontmatter fields (title, tags, topics, sources). Uses word-level matching: any query term triggers a match, so multi-word queries like `"AI agents skills context windows"` return all notes matching any of those terms. Obsidian search alone is insufficient because it only searches note body content.

**If no relevant topics found:** Before creating the note, check if a topic note already exists for this subject area. If not, create one first (write to `Wiki/Topics/<Topic Name>.md` using the topic template), then reference it. Never leave `topics:` empty — every concept/entity must connect to at least one topic note.

### Step 3 — Read Relevant Compiled Wiki Notes
**Action:** Use obsidian-cli to read only the most relevant compiled wiki notes from Step 2 results.

```bash
obsidian read path="$WIKI_FOLDER/<Note Name>.md" vault="<vault-name>"
Replace `$WIKI_FOLDER` with the folder from config's `tag_routing` for this tag.
```

Open only the most relevant notes — not all Raw context. Understand what already exists before creating new notes. This lets you:
- Identify if a note should be **updated** (add source references) vs. created new
- Find existing wikilinks to connect into

### Step 4 — Pre-Write Isolation Check
**Action:** Before calling `obsidian_write` for any compiled note, verify isolation and provenance. This check prevents cross-source contamination (content from Source A bleeding into notes written for Source B) and ensures all wikilinks resolve within the target vault only.

**Run before every `obsidian_write` call:**
1. **Source derivation check:** Verify all body content in the note derives ONLY from the declared source(s). No content should originate from a different raw file. If processing multiple sources in parallel, confirm each note's text matches its own source — not a sibling source.
2. **Wikilink scope check (C12 pre-check):** Scan all wikilinks in the note's frontmatter and body. Every `[[wikilink]]` must resolve within this vault's `wiki_root`. If any link points outside the current vault, FIX before writing.
3. **Sources array validation:** Verify `sources:` in frontmatter contains ONLY wikilinks to raw sources from the current batch. No stale or cross-vault source paths allowed.
4. **Template compliance:** Confirm the note starts from the correct vault template (read in Step 5's pre-step). All required sections (`## Related`, `## Sources`) are present. Frontmatter arrays use block-array syntax (not scalar).

**If any check fails:** Do NOT call `obsidian_write`. Fix the issue, re-verify, then proceed.

**This check is lightweight:** It uses `grep` on the note content you just prepared — no tool calls, no external reads. It takes seconds and prevents catalog corruption from cross-source contamination.

### Step 5 — Create or Update Wiki Notes
**Action:** Use native tools to create focused wiki notes in the correct folder per tag routing.

**MANDATORY: Read template before writing.** Every new note MUST start from the corresponding vault template. This ensures consistent frontmatter, required sections (`## Related`, `## Sources`), and proper array formatting.

1. **Read the template** for this note's tag:
   ```bash
   cd <wiki-root> && cat $TEMPLATES_DIR/<tag>-note.md  # e.g., concept-note.md, entity-note.md
   ```
   Replace `$TEMPLATES_DIR` with the value from config `paths.templates_dir`. If config shows `_templates`, run: `cat _templates/concept-note.md`.

2. **Use the template as your base structure** — keep frontmatter fields, section headers (`## Related`, `## Sources`), and any scaffolding text. Replace only the content placeholders.

3. **Fill in real values** — replace all `{{Placeholders}}` with actual content, populate frontmatter arrays (`sources:`, `topics:`) before calling write.

4. **Write via native tool:**
   ```
   obsidian_write note="$WIKI_FOLDER/<Note Name>.md" content="<full note with frontmatter>" vault="$VAULT"
   ```

Or via CLI (requires inline content expansion — prefer native tools):
```bash
obsidian create path="$WIKI_FOLDER/<Note Name>.md" vault=<vault-name> overwrite content="$CONTENT"
Replace `$WIKI_FOLDER` with the folder from config's `tag_routing` for this tag.
```

**Tag routing** (from config `tag_routing` — defined per-vault in AGENTS.md's `tag_routing` checklist field):
| Tag | Folder (from config) | What goes here |
|-----|----------------------|----------------|
| `topic` (default) | from config (`Wiki/Topics`) | Broad subject areas (e.g., "LLM Wiki") |
| `concept` (default) | from config (`Wiki/Concepts`) | Discrete ideas, definitions, mechanisms |
| `entity` (default) | from config (`Wiki/Entities`) | People, organizations, tools |
| `project` (default) | from config (`Wiki/Projects`) | Initiatives with scope and status |
| *(vault-specific)* | from config | Custom tags: vaults may define additional mappings in AGENTS.md `tag_routing` |

Use `discover_config()` or `get_config()` to get the routing table — it may differ per vault. Validate new tags against config's `allowed_compiled_tags`. |

**Core rules (strictly enforced):**
- **One concept per note.** Extract genuine knowledge — focus on depth, relevance, and completeness per concept rather than filling a template.
- **A single raw source may contain multiple distinct concepts, tools, or architecture decisions — create one separate note per concept.** Do not summarize everything into a single shallow document.
- **Every note must have proper frontmatter** with `tags`, `topics` (wikilinks to relevant topic notes), `sources` array, and `source_count`
- **The `topics` field MUST contain at least 1 wikilink to an existing topic note.** If no relevant topics found, create a new topic note first (write to `Wiki/Topics/<Topic Name>.md`), then reference it. Never leave empty.
- **Every note must include `## Related` and `## Sources` sections** in the body
- **Topics must be genuinely relevant.** Each wikilink should represent a subject area the note actually covers — not generic system names.

**Enforcement checklist before writing:**
1. **Read template** — `cat $TEMPLATES_DIR/<tag>-note.md` (e.g., `_templates/concept-note.md`). Verify the template has frontmatter, `## Related`, and `## Sources` sections. Use this as your base structure.
2. Analyze for distinct knowledge items — does this source cover multiple concepts, tools, or decisions? Create separate notes if needed.
3. **Populate `topics:`** — use Step 2 catalog results to pick specific, relevant topic titles. Use the **exact title text** from the target note's frontmatter `title:` field — NOT wikilinks. Obsidian renders `- [[wikilink]]` in YAML frontmatter as triple brackets (broken display). Use raw plain text only, e.g., `- Voxel Game Development`. If no relevant topics found, create one first (write to `Wiki/Topics/<Topic Name>.md` using the template), then reference it. Never leave empty.
4. **Replace ALL frontmatter placeholders** — every YAML array field (`sources: []`, `topics: []`) must be filled with real values **BEFORE calling obsidian_write**. The content string's YAML frontmatter is what gets written as note properties — body text sections (`## Sources:`) are NOT parsed as frontmatter. **This is the #1 cause of ingest failures.** See critical warning below.
5. Replace all `{{Placeholders}}` with real content — remove template scaffolding text
6. Both `## Related` and `## Sources` sections present at the end (templates include these)

7. **Topic relevance gate:** After writing, verify topics are specific and relevant (not generic system names). If >max_topics from checklist, trim to most relevant.

**⚠️ CRITICAL — obsidian_write parsing behavior:**
The `obsidian_write` tool reads ONLY the YAML frontmatter block (between `---` delimiters) to set note properties. Body text sections like `## Sources:` are completely ignored for property assignment. If you write:

```yaml
sources: []
...
---
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

### Step 6 — Validate with Wiki Tool (Single Vault)

**Action:** Run build, lint, and source-lint to enforce the wiki's schema contract.

```bash
python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint
```

- **build** — rebuilds `catalog.jsonl`, `index.md`, and per-folder indexes from all wiki notes. Also auto-fixes empty `sources:` arrays by populating them from body text under `## Sources:` — this is a **safety net, not a substitute** for proper frontmatter. Always fill sources in YAML before writing.
- **lint** — validates compiled note frontmatter: tag validity, dates (YYYY-MM-DD), source paths resolve on disk (`source_count` matches array length), required sections present (both `## Related` AND `## Sources` — missing either fails the check), topics consistency (concept/entity must have ≥1 topic, ≤max_topics from checklist).
- **source-lint** — validates raw source frontmatter (title, reference/source present, created date format) and coverage state (processed sources must have `covered_by` entries).

If ANY check fails, fix the issues and repeat. This is your quality gate — Python scripts enforce rules Obsidian doesn't know about (source resolution, schema compliance). Do NOT skip `source-lint` — it catches issues that lint doesn't (raw source frontmatter, coverage state).

### Step 6b — Post-Ingest Parallel Validation (Multi-Vault)

**Rationale:** When processing 3+ vaults sequentially (same session), running validation in parallel reduces total time from `sum(validation_time)` to `max(validation_time)`. Each vault's validation is independent (different wiki_root, no shared state).

**Post-ingest validation:** After Steps 0–9 complete for all selected vaults, run `python3 scripts/wiki_tool_all.py validate-all` on each vault in parallel. Report failures per-vault independently.

**Command:**
```bash
python3 scripts/wiki_tool_all.py validate-all [--vault A,B,C]
```
This discovers all vaults from project config, runs `build + lint + source-lint` per vault with a 90-second timeout each, and reports consolidated results.

**Result handling:**
- **All vaults pass:** Proceed to Step 10 (commit each individually)
- **One or more fail:** The script reports which vaults failed and why. User decides:
  - Fix the failing vault(s) and re-validate
  - Commit passing vaults now, defer failing ones (use `--no-verify` on pre-commit hook)
  - Abort all and fix everything before any commit

**Permission-aware:** The script checks vault permissions from config. Vaults with `read` permission can run lint/source-lint but NOT build (write operation). Read-only vaults (`["read"]`) are validated for schema quality but skipped for build.

### Step 7 — Update Source Manifest
**Action:** Scan raw sources and update the manifest with coverage state.

```bash
python3 scripts/wiki_tool.py source-scan --update --accept-covered
```

This tracks which raw sources have been processed and how many wiki notes they produced. **Important:** `--accept-covered` validates that all wiki notes in `covered_by` still exist on disk and automatically removes stale entries. Sources with no valid coverage are marked unprocessed.

**Note:** Image files processed in Step 0 (including image-only markdown routed through VL) are not tracked by this manifest (they have no frontmatter and were never stored as markdown in the configured raw paths). Notes created from images may reference the image file path in their `sources` array if relevant, but these will not appear in source-scan output.

### Step 8 — Log the Change
**Action:** Use `wiki_tool.py log` to append a timestamped entry if the ingest meaningfully changed the Wiki (new notes created, existing notes updated).

```bash
python3 scripts/wiki_tool.py log --title "<short title>" --details "<what was affected and why>"
```

Only log if meaningful changes were made — not for every minor update. The entry should describe what files were affected and why.

### Step 9 — Commit (Git)
**Action:** Use git to commit all changes. The pre-commit hook automatically runs `build + lint + source-lint` as a final safety gate.

```bash
git add -A && git commit -m "<message>"
```

Git is outside Obsidian's scope — obsidian-cli can't touch it. The pre-commit hook provides the last line of defense before changes land in history.

**Multi-vault workflow:** When processing multiple vaults (each a separate git repo):

1. **Steps 0–9 per vault:** Each vault processes independently in its own wiki_root
2. **Step 6b (parallel validation):** After all vaults complete Steps 0–9, run `build + lint + source-lint` in parallel across all vaults (see Step 6b above)
3. **Commit:** For each passing vault, commit individually:
```bash
cd $VAULT_A_DIR && git add -A && git commit -m "<message>"
cd $VAULT_B_DIR && git add -A && git commit -m "<message>"
```

Each vault's pre-commit hook runs independently for its own repo. The parallel validation in Step 6b gives you a consolidated report before any commits; the pre-commit hook is a final safety net against changes made between Step 6b and the actual commit.

**Commit strategy with mixed results:** If some vaults pass validation but others fail:
- **Option A (recommended):** Commit passing vaults immediately, defer failing ones. Fix failing vaults and re-validate in the next session.
- **Option B (strict):** Abort all commits. Fix ALL vaults before any commit lands.
- **Option C (force):** Use `git commit --no-verify` on failing vaults to bypass pre-commit hook (not recommended — only use if you're confident the issues are minor).
