---
name: llm-wiki-ingest
description: Ingest new sources and create or update compiled Wiki notes following the ingest workflow. Uses Obsidian CLI for all vault file operations to prevent YAML corruption and wikilink errors.
---

## When triggered
**Invoking this skill means executing the workflow, not discussing it.** The very first action is vault selection.

**Check for a vault name in the invocation arguments (text after the `<skill>` block).** If one was provided, use it directly. Otherwise, list available vaults and ask the user to choose.

Do not describe, explain, or summarize the skill before performing this step.

## When to use
The user adds a new source, wants to process raw content into wiki notes, or asks you to create/update compiled Wiki notes.

## Prerequisites
- **Obsidian must be running** — all vault operations use the Obsidian CLI which connects via Chrome DevTools Protocol
- **Vault must be identified before any operation** — see Vault Selection below

## Pre-flight Check (Required Before Vault Selection)
**Before attempting vault selection, verify config is usable.** If it's missing or empty, offer setup.

1. **Check vaults:**
   ```bash
   cd <wiki-root> && python3 scripts/wiki_shared.py vaults 2>&1
   ```

2. **If output lists vaults** (e.g., `Core [read,write,...]`): proceed to Vault Selection.

3. **If output is empty or says "No project config":**
   - Tell the user: "Config not found or has no vaults declared (.llm-wiki-config/config.json). Without it, wiki operations can't proceed."
   - Ask: "Would you like to run the setup wizard? It will discover your Obsidian vaults and let you assign permissions (read, write, ingest, maintain)."
   - **If user agrees:** spawn a subagent to run setup:
     ```javascript
     subagent({
       agent: "scout",
       task: "Run the llm-wiki-setup workflow to create .llm-wiki-config/config.json. Walk up from wiki root, discover vaults via obsidian CLI, guide user through permission selection, write config file.",
       skill: "llm-wiki-setup"
     })
   ```
   - **If user declines:** stop and explain wiki operations require a project config.

## Vault Selection (Required Before Any Operation)
This skill is **vault-agnostic**. It works with any Obsidian vault that contains an LLM Wiki structure.

**FIRST ACTION: Before performing ANY step in this workflow, identify which vault to use. Do not skip this or assume a vault from context.**

### How to select a vault:
**FIRST — Check the invocation arguments (text after the `<skill>` block).** If one or more vault names are present, parse them as space-separated values. The special value `all` selects every declared vault.

**Single-vault shortcut:** If the Pre-flight Check returns exactly one vault, skip selection and use it directly. No confirmation needed.

1. **If the user explicitly named vault(s)** (e.g., "ingest into <vault-name>", `/llm-wiki-ingest <vault-1> <vault-2>`), or they were provided as invocation arguments, use those names directly. The special value `all` means every declared vault.
   ```bash
   obsidian ... vault="<name>"
   ```
2. **Otherwise, use the list from Pre-flight Check** (already ran `wiki_shared.py vaults`). If there's more than one vault, present it and ask: "Available vaults (from project config): [list]. Which one(s) do you want to work with? (Type **all** to select every vault.)"

3. **If the user mentions a wiki by name** (e.g., "the <vault-name> wiki"), do NOT assume it maps to a vault with the same name — discover from config and let them select.

**Once identified, use that exact vault name for every `obsidian` command in this workflow.** If multiple vaults were selected, run the full Steps 1–9 for each one sequentially. Do not change a vault mid-workflow.

**Validation — after selecting, verify every chosen vault is declared.** The list from Pre-flight Check already confirmed these are valid. For each selected name, confirm it appears in that list. If a vault was typed (from args or interactive answer) but not found:
- **Single wrong name:** tell the user it's not declared in project config, show available vaults, and ask for a correction.
- **Some wrong names among multiple:** tell the user which are valid and which aren't. Ask if they want to proceed with only the declared vaults or correct.
- **`all`:** always valid — it expands to every declared vault in the config.

## Reference
- `AGENTS.md` — Ingest Workflow section, Core Rules, directory structure (at wiki root)
- `_templates/*.md` — frontmatter schemas for each note type
- `scripts/wiki_tool.py` — build, lint, search-catalog, source-scan, log
- `scripts/wiki_shared.py` — shared utilities: config discovery (`config`, `discover-config`), project config discovery (`find_project_config`, `load_project_config`), VL discovery (`discover`), model resolution (`models <task>`), defaults/overrides CLI
- `llm-wiki-setup` skill — invoked via subagent tool with `skill: "llm-wiki-setup"` when config is missing
- `.llm-wiki-config/config.json` — project-level vault declarations and permissions (source of truth)
- `Schema/.llm-wiki-cache.json` — per-project shared cache (defaults, VL discovery results, task overrides, config)

## Config Discovery (Required Before Vault Operations)
The skill uses **config-driven paths and permissions** from `wiki_shared.py`. Always discover config before scanning or writing:
```bash
cd <wiki-root> && python3 scripts/wiki_shared.py config --force 2>&1
```
Returns JSON with:
- `permissions` — what operations are allowed (`read`, `write`, `ingest`, `maintain`). Skip write/ingest if not present.
- `raw_paths` — **absolute paths** to raw source directories (from config). Always uses --force so values are fresh.
- `tag_routing` — maps folder names to tags (e.g., `{"Topics": "topic", "Concepts": "concept"}`). Per-vault — defined in AGENTS.md's `tag_routing` checklist field. Defaults to standard map if absent.
- `allowed_compiled_tags` — valid tags for wiki notes (discovered from tag_routing)
- `paths` — relative paths to `_templates`, `Wiki`, `Schema` (relative to wiki root)

The `--force` flag is always used in this skill to guarantee fresh paths. The staleness-refresh path in `discover_config()` also updates raw_paths from actual directories even without --force, but --force is the reliable option.

**Pre-flight check already verified config exists** (see Pre-flight Check above).

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

## Wiki Tool Operations (Python)
These operations are **wiki-specific** and run from the wiki directory. They enforce schema rules Obsidian doesn't know about:

| Command | Purpose |
|---------|---------|
| `python3 scripts/wiki_tool.py search-catalog --query "..."` | Search structured catalog index (title, tags, topics, sources). Uses word-level matching — any query term triggers a match. No need to run multiple queries for multi-word searches.
| `python3 scripts/wiki_tool.py build` | Rebuild catalog.jsonl, index.md, per-folder indexes from all wiki notes |
| `python3 scripts/wiki_tool.py lint` | Validate frontmatter schema: tags, dates (YYYY-MM-DD), source paths resolve, source_count consistency, required sections |
| `python3 scripts/wiki_tool.py source-scan --update --accept-covered` | Scan configured raw paths, update manifest with coverage state and source counts. Validates all wiki notes in `covered_by` still exist on disk (removes stale entries automatically). |

Run these from the wiki root directory (the same directory that contains `AGENTS.md`, `_templates/`, and `scripts/wiki_tool.py`).

## Workflow

**Multi-vault note:** When multiple vaults are selected, each is an independent repo. Steps 0–9 run completely for the first vault before moving to the next — no shared state, no cross-vault references. If Step 1 involves a new source (URL/file) provided by the user, that same cleaned content is written to each vault's first configured raw path (from config `raw_paths`).

### Pre-flight Constraints — Execute Before Any Step
**These are mandatory gates. Do not skip.** Each prevents a known failure mode.

| Gate | What to verify | Command / Action |
|------|---------------|------------------|
| **CFG-1** | Config loaded before any write | `python3 scripts/wiki_shared.py config --force` — store paths in variables |
| **CFG-2** | Vault rules parsed (max_topics, required_sections, allowed_tags) | From AGENTS.md checklist section |

---
### Step 0 - Check for Pending Sources
**Action:** Before asking the user for a source, discover vault config and check each validated vault's raw paths for files that need processing.

**Config Discovery:** Before scanning, discover the vault's config to get its permissions and raw paths:
```bash
cd <wiki-root> && python3 scripts/wiki_shared.py config --force 2>&1
```
This returns JSON with `permissions` (e.g., `["read", "write", "ingest"]`) and `raw_paths` (e.g., `["Raw/Source", "Raw/Sources"]`). If the vault has only `"read"` permission, skip all write/ingest operations — report "Vault is read-only (no ingest/write permission)" and move to the next vault.

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
- **`provider: "<vl-provider>", model_id, base_url populated`** — use the discovered local engine. Read values from cache output.
- **All null/empty** — No VL model found locally. Inform the user that image processing is unavailable and continue with markdown sources only.

To set defaults (so all skills use consistent models):
```bash
python3 scripts/wiki_shared.py set-default vl_provider <vl-provider>
python3 scripts/wiki_shared.py set-default text_model_id "<text-model-id>"
```
To set per-task overrides:
```bash
python3 scripts/wiki_shared.py set-override image_ingest vl_model_id "<vl-model-id>"
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
  Files that fail these checks should be fixed in place (clean the frontmatter, normalize format) before proceeding. Files that are empty or contain only images/embeds without text should be handled per the **Image-Only Markdown Detection** rule below.

**Image-only markdown detection (`--keep-images` flag):** After source validation, if the `--keep-images` flag was passed to ingest, check each markdown file whose body contains only image embeds (`![](...)`) with no substantive text. These are markdown wrappers around images (e.g., YouTube clipping screenshots). For each detected file:
1. Extract the image paths from `![](...)` syntax in the body.
2. Route each embedded image through VL processing (same path as raw images discovered on disk in Step 0). Pass the extracted image paths to VL subagents.
3. The VL output flows through the Consolidate step, then Steps 2–9 as normal.

If `--keep-images` is NOT set, continue with current behavior: markdown files whose bodies become empty after cleaning are treated as sources to be cleaned and may be skipped/deleted if they contain no text. The default behavior (no flag) preserves backward compatibility — image-only sources are cleaned normally and may be discarded if empty after cleaning.
- **Other files**: Skip unless clearly a usable content source.

**Image Processing:** Each unprocessed image must be analyzed and converted into wiki notes. Choose the approach that matches your capabilities:

- **If you have VL/image reading capability:** read each image directly with your `read` tool, then write wiki notes using the output format rules below.
- **If you do NOT have VL capability:** spawn a subagent with the `llm-wiki-vl` skill for each image. The child reads images via its own `read` tool and produces note text that you capture in `$VL_OUTPUT_FILE`. The VL subagent must NEVER write files to disk — it only produces text output.

**Model warm-reuse (subagent path only):** The cache flag `defaults.agent_has_vision: True` plus the task override for `image_ingest` keep the ~20GB VL model loaded between subagent calls. After one initial cold start (60-90s), subsequent calls reuse the warm model (~10-20s). Spawn each subagent as a separate call — no batching. If you are analyzing images directly, this warm-reuse does not apply.

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
os.chdir("<wiki-root>")  # project's wiki root from config discovery
from scripts.wiki_shared import resolve_model
model_info = resolve_model("image_ingest")
provider = model_info.get("provider")
model_id = model_info.get("model_id")
base_url = model_info.get("base_url")
if not provider or not model_id:
    print(f"ERROR: VL model not configured. Set vl_provider and vl_model_id in .llm-wiki-config/config.json.")
    sys.exit(1)
print(f"{provider}/{model_id}")  # e.g., <vl-provider>/<vl-model-id>
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
  model: "<vl-model-id>",
  skill: "llm-wiki-vl",
  output: "$VL_OUTPUT_FILE"
})
```

**Key details:**
- **Delegation is optional.** If you can read images yourself, do so directly. Otherwise spawn a subagent with `llm-wiki-vl` skill — the child reads images via its own `read` tool and produces note text that you capture in `$VL_OUTPUT_FILE`. The VL subagent must NEVER write files to disk.
- The `llm-wiki-vl` skill (injected into the subagent) provides output format rules, tag routing, frontmatter schema, and metadata fields (SOURCE_NOTE, IMAGE_INDEX, CONSOLIDATION_CONFIDENCE).
- Existing topics are passed as context so the subagent can populate `topics` with real wikilinks.
- Real image filenames are passed so the subagent uses correct paths in `sources` (no hallucination).
- **Keep model warm (subagent path only):** The cache flag `defaults.agent_has_vision: True` plus the task override for `image_ingest` keep the VL model loaded between subagent calls. Each subsequent call reuses the warm model (~10-20s) instead of cold starting (~60-90s). If the model is unloaded (e.g., after a long pause), accept one cold start, then subsequent calls will be fast.

VL output flows through the **Consolidate** step (below) before any notes are written. Do NOT write VL output directly to disk — consolidate evaluates merge/split decisions and produces a decision document that you execute.

**No VL model found:** If discovery returns no `provider`/`model_id`, and you do not have VL capabilities yourself, inform the user: "No vision-capable model is available. Image processing will be skipped — markdown sources can still be ingested." Do NOT continue silently.

**Cold-start warning (subagent path only):** The subagent's VL model load takes ~60-90s (cold start on local engine). The subagent itself may take 30–120s more for inference + note generation. Use `async: true` if you want to continue other work while waiting.

**Verbose output handling (subagent path only):** If the subagent's output in `$VL_OUTPUT_FILE` contains verbose reasoning or preamble text instead of clean `---NOTE_BOUNDARY---` separated notes, extract the note drafts from within (they appear as structured markdown blocks with `---YAML---` frontmatter) or rewrite them manually based on the VL analysis. The `llm-wiki-vl` skill enforces clean output but cannot guarantee it for all VL models.

---

### Consolidate — Evaluate VL Output Before Writing Notes
**Action:** After all VL subagents complete, spawn a consolidation subagent with the `llm-wiki-consolidate` skill. This step determines which VL outputs become notes, which should be merged or updated, and which need human review.

**⚠️ SKIP GATE:** If no VL images were found during Step 0 discovery AND `$VL_OUTPUT_FILE` is empty or missing, skip consolidation entirely and proceed directly to Steps 1–9. Do NOT spawn a consolidate subagent when there is no VL output to evaluate.

**Preparation:** Before spawning consolidate, strip VL metadata lines from `$VL_OUTPUT_FILE` so the consolidator reads clean note text:
- **Metadata pattern:** Lines matching `^---(SOURCE_NOTE|IMAGE_INDEX|CONSOLIDATION_CONFIDENCE|CONSOLIDATION_REASON):\s*.+$`
- **Action:** Remove matching lines from the file. These metadata fields are passed separately to consolidate (not embedded in note text).
- **Graceful fallback:** If no metadata lines found, proceed normally — consolidate uses its own rules for evaluation.
- **Edge case:** Metadata values may contain colons (e.g., `SOURCE_NOTE: tutorial-install.md`). The regex handles this via greedy capture after the first colon.

**Spawn consolidate subagent:**
```bash
subagent({
  agent: "default",
  task: "Evaluate VL output and source mapping. Produce a consolidated decision document.",
  skill: "llm-wiki-consolidate",
  output: "$CONSOLIDATE_OUTPUT_FILE"
})
```

**Context to pass:** The orchestrator provides the consolidate subagent with:
- `$VL_OUTPUT_FILE`: Path to VL output (already stripped of metadata lines)
- Source mapping: Which raw source file each image came from (from Step 0 discovery)
- Pre-grouping hints: Filename pattern heuristics (sequential numbering → same group), batch ID
- Optional catalog context: List of existing topic titles in the target vault (for R5: detect existing topics)

**Read decision document:** After consolidate completes, read `$CONSOLIDATE_OUTPUT_FILE` to get:
- `notes_written`: Notes that should be created (use `obsidian_write`)
- `notes_updated`: Existing notes to append content to (use `obsidian_append`)
- `ambiguous_cases`: Cases consolidate couldn't resolve confidently — review and decide manually
- `summary`: Quick status for progress tracking (`total_vl_outputs_evaluated`, `notes_created`, `notes_updated`, etc.)

**Execute decisions:** For each entry in the decision document:
- `notes_written` → call `obsidian_write` with path, tags, topics from the entry
- `notes_updated` → call `obsidian_append` with path and new content from VL output
- `ambiguous_cases` → review each case, decide: merge, keep separate, or reject. Record your decision.

**Key constraint:** Consolidate does NOT write notes to disk — it only produces the decision document. You (the orchestrator) execute all writes via `obsidian_write`/`obsidian_append`. This maintains vault isolation and gives you full control over what gets written.

---

### Step 1 — Clean & Store Raw Source
**Action:** Write cleaned Markdown into the vault's configured raw paths (from config `raw_paths`) using the native tools. Use the first writable path in the list (e.g., `Raw/Sources/`). **Skip this step for image files** — they bypass cleaning entirely and go from VL analysis (Step 0) directly to Steps 2–9.

**⚠️ GATE — Source Body Integrity (C0 + C11):** After cleaning, you MUST verify:
- **Read back the cleaned file** (first 50 and last 50 lines). Confirm no timestamp patterns (`**X:XX** ·`, `HH:MM:SS - Title`), promo lines, or image embeds remain.
- **Line count preserved within tolerance**: If body dropped >50% of original lines, RE-DO cleaning with in-context editing (no script). Only deterministic transforms allowed: remove timestamps, chapter markers, `[music]` fillers, promo links.
- **Hard fail**: If C0 triggers (timestamp/promo patterns remain) or body integrity fails, do NOT proceed to Step 2. Fix immediately, re-verify.

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
- **If `--keep-images` flag is set:** DO NOT remove embeds. Skip cleaning and route this source to VL processing (see Image-only markdown detection above).
- **If `--keep-images` is NOT set:** Skip this source entirely and log "skipped (image-only, --keep-images not set)". Do NOT delete the file — move it to a separate location for manual review if needed.

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

### Step 6 — Validate with Wiki Tool
**Action:** Run build, lint, and source-lint to enforce the wiki's schema contract.

```bash
python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint
```

- **build** — rebuilds `catalog.jsonl`, `index.md`, and per-folder indexes from all wiki notes. Also auto-fixes empty `sources:` arrays by populating them from body text under `## Sources:` — this is a **safety net, not a substitute** for proper frontmatter. Always fill sources in YAML before writing.
- **lint** — validates compiled note frontmatter: tag validity, dates (YYYY-MM-DD), source paths resolve on disk (`source_count` matches array length), required sections present (both `## Related` AND `## Sources` — missing either fails the check), topics consistency (concept/entity must have ≥1 topic, ≤max_topics from checklist).
- **source-lint** — validates raw source frontmatter (title, reference/source present, created date format) and coverage state (processed sources must have `covered_by` entries).

If ANY check fails, fix the issues and repeat. This is your quality gate — Python scripts enforce rules Obsidian doesn't know about (source resolution, schema compliance). Do NOT skip `source-lint` — it catches issues that lint doesn't (raw source frontmatter, coverage state).

### Step 7 — Update Source Manifest
**Action:** Scan raw sources and update the manifest with coverage state.

```bash
python3 scripts/wiki_tool.py source-scan --update --accept-covered
```

This tracks which raw sources have been processed and how many wiki notes they produced. **Important:** `--accept-covered` validates that all wiki notes in `covered_by` still exist on disk and automatically removes stale entries. Sources with no valid coverage are marked unprocessed.

**Note:** Image files processed in Step 0 are not tracked by this manifest (they have no frontmatter and were never stored as markdown in the configured raw paths). Notes created from images may reference the image file path in their `sources` array if relevant, but these will not appear in source-scan output.

### Step 8 — Log the Change
**Action:** Use `wiki_tool.py log` to append a timestamped entry if the ingest meaningfully changed the Wiki (new notes created, existing notes updated).

```bash
python3 scripts/wiki_tool.py log --title "<short title>" --details "<what was affected and why>"
```

Only log if meaningful changes were made — not for every minor update. The entry should describe what files were affected and why.

### Step 9 — Commit (Git)
**Action:** Use git to commit all changes. The pre-commit hook automatically runs `doctor + build + lint` as a final safety gate.

**⚠️ GATE — Pre-commit explicit lint (C10):** Before running `git commit`, explicitly run the validation scripts. Do NOT rely on pre-commit hooks alone — they are a safety net, not your primary quality gate.

```bash
python3 scripts/wiki_tool.py build && python3 scripts/wiki_tool.py lint && python3 scripts/wiki_tool.py source-lint
```

Only proceed to `git add -A && git commit` if ALL three checks pass. If any fail, fix the issues and re-run.

```bash
git add -A && git commit -m "<message>"
```

Git is outside Obsidian's scope — obsidian-cli can't touch it. The pre-commit hook provides the last line of defense before changes land in history.
