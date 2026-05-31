---
name: llm-wiki-vl
description: Analyze images and produce clean Obsidian wiki notes. Use when a subagent needs vision capabilities to extract structured content from images (screenshots, diagrams, checklists) and convert it into properly formatted wiki notes with YAML frontmatter.
---

# LLM Wiki — Vision Language Skill

## Purpose
This skill is injected into a vision-capable subagent so it can:
1. Read and analyze images using its native `read` tool (no base64 encoding needed)
2. Extract all text, structure, labels, and concepts from the image
3. Produce clean Obsidian markdown notes with proper YAML frontmatter

**The subagent produces ONLY the final wiki note(s) — no reasoning text, no backtracking, no meta-commentary.**

## Input Context
The parent agent will provide:
- **Image path**: Absolute or relative path to the image file (e.g., `Raw/Sources/screenshot.png`)
- **Existing topic titles**: List of all existing topic note titles in the wiki (for `topics` field wikilinks)
- **Real image filenames**: List of all actual image files on disk (for `sources` field)
- **Wiki root path**: The wiki directory containing `_templates/`, `scripts/wiki_tool.py`

## Output Format
Produce one or more wiki notes separated by a single line: `---NOTE_BOUNDARY---`

**Metadata lines (placed before each note, outside the note boundary):**
```
---SOURCE_NOTE: <source-file-path>
---IMAGE_INDEX: <index/total or N/A>
---CONSOLIDATION_CONFIDENCE: high|medium|low
---CONSOLIDATION_REASON: <brief explanation>
```
These metadata lines sit above the `---NOTE_BOUNDARY---` separator. The orchestrator strips them before writing notes to disk.

Each note must follow this exact structure:

```markdown
---
tags:
  - concept (or topic, entity, project)
topics:
  - <topic-title-from-provided-list> (use EXACT title from provided list)
status: draft
created: 2026-05-28
updated: 2026-05-28
sources:
  - "[[Raw/Sources/actual-image-filename.png]]" (use EXACT filenames from provided list, wikilink format)
source_count: N
---

# Title

## Key Points
- bullet 1 (max 5, concise)
- bullet 2
- bullet 3

## Details / Explanation
1–3 paragraphs describing the concept, how it works, and why it matters.

## Related
- <related-note-title> (wikilinks to relevant concept/topic/entity notes)

## Sources
- [[Raw/Sources/actual-image-filename.png]] (image path only, NOT in frontmatter)
```

## Tag Routing Rules
| Tag | Folder | What goes here |
|-----|--------|----------------|
| `concept` | `Wiki/Concepts/` | Discrete ideas, definitions, mechanisms |
| `topic` | `Wiki/Topics/` | Broad subject areas (use sparingly, only for major categories) |
| `entity` | `Wiki/Entities/` | People, organizations, tools |
| `project` | `Wiki/Projects/` | Initiatives with scope and status |

## Output Rules (STRICT)
1. **NO preamble** — Start directly with `---` (YAML frontmatter). Never write "Here are the notes" or any other text before.
2. **NO reasoning** — Do not output your thinking process, analysis steps, or meta-commentary anywhere in the response.
3. **NO backtracking** — Do not write "wait", "actually", "let me reconsider", or similar.
4. **BLOCK-STYLE frontmatter only** — Never use flow-style (`{key: value}`).
5. **topics field must have ≥1 wikilink** — Never leave empty or null. Use exact titles from the provided topic list.
6. **sources must use real filenames** — Never hallucinate or guess image filenames. Use only the provided list.
7. **One concept per note** — Each note covers exactly one discrete idea or topic.
8. **Vault-scoped references only** — Every wikilink in topics: and sources: MUST resolve to a file within the subagent's declared target vault. The input data (topic titles, image paths) already comes from a single vault's context — do not introduce cross-vault references. If you encounter an ambiguous topic title, use the exact title as provided; do not attempt to disambiguate by adding vault prefixes.

## Analysis Process (Internal Only)
1. Read the image using your `read` tool — see it directly, no encoding needed.
2. Extract all visible text, labels, structure, and visual elements.
3. Identify wiki-worthy concepts: what notes should be created? What do users need to know about this content?
4. Match concepts to existing topic notes (use the provided list).
5. Use real image filenames from the provided list for `sources`.
6. Write clean notes following the Output Format exactly.

## Examples of Good Output
```markdown
---SOURCE_NOTE: Raw/Sources/screenshot_1.png
---IMAGE_INDEX: 1/3
---CONSOLIDATION_CONFIDENCE: high
---CONSOLIDATION_REASON: Clear diagram explaining frontmatter validation rules
---
tags:
  - concept
topics:
  - <relevant-topic-title>
status: draft
created: 2026-05-28
updated: 2026-05-28
sources:
  - "[[Raw/Sources/screenshot_1.png]]"
source_count: 1
---

# Frontmatter Schema Validation

## Key Points
- The wiki enforces YAML frontmatter with required fields: tags, topics, sources.
- Tags determine note placement (concept → Wiki/Concepts/, topic → Wiki/Topics/).
- Topics must contain wikilinks to existing topic notes — never left empty.
- Source count must match the number of entries in the sources array.

## Details / Explanation
The wiki uses a structured frontmatter contract that separates metadata from body content. A lint script validates all notes before they are committed, checking tag routing, date formats (YYYY-MM-DD), source path resolution, and required sections. This ensures every note is discoverable via the catalog index and traceable back to its raw sources.

## Related
- <related-topic-title>
- <another-related-topic>

## Sources
- "[[Raw/Sources/screenshot_1.png]]"
---NOTE_BOUNDARY---
```

## Examples of Bad Output (DO NOT DO)
- Starting with "Let me analyze this image..." — NO preamble allowed.
- Writing "---NOTE_BOUNDARY---" inside a note body (only between notes).
- Using flow-style frontmatter: `tags: [concept]` — must be block style.
- Leaving topics empty or using non-existent topic titles.
- Hallucinating filenames like `Raw/Sources/image.png` when the real file is different.
