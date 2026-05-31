---
name: llm-wiki-consolidate
description: Evaluate VL subagent output and source mapping to produce a structured decision document for note creation, update, or merge. Use after VL batch completes and before text source processing (Steps 1-9).
---

# LLM Wiki — Consolidate Skill

## Purpose
Evaluate VL (Vision Language) subagent output alongside the orchestrator's source mapping to produce a structured decision document. This skill determines which VL outputs should become notes, which existing topics need updating, and which cases require human review.

**This skill does NOT write notes to disk.** It produces a decision document that the orchestrator executes via `obsidian_write`, `obsidian_append`, or manual review.

## Input
The orchestrator provides:
- **$VL_OUTPUT_FILE**: Path to the VL subagent's output file (contains notes separated by `---NOTE_BOUNDARY---`, each preceded by metadata lines)
- **$SOURCE_MAPPING**: JSON describing source-to-vault relationships (provided by orchestrator, not VL subagent)
- **Optional catalog context**: List of existing topic titles in the target vault (for R5: detect existing topics)

## Output
Produce a JSON decision document to `$CONSOLIDATE_OUTPUT_FILE` with this structure:

```json
{
  "notes_written": [
    {
      "action": "create",
      "path": "Wiki/Concepts/frontmatter-schema.md",
      "tags": ["concept"],
      "topics": ["<topic-title>"],
      "source_note": "<vl-metadata-source>",
      "image_index": 1,
      "confidence": "high",
      "merged_from": []
    }
  ],
  "notes_updated": [
    {
      "action": "update",
      "path": "Wiki/Concepts/existing-note.md",
      "reason": "VL image adds new detail to existing concept"
    }
  ],
  "ambiguous_cases": [
    {
      "reason": "VL flagged cross-topic overlap with low confidence",
      "vl_metadata_source": "<source>",
      "image_index": 2,
      "suggested_action": "human_review"
    }
  ],
  "summary": {
    "total_vl_outputs_evaluated": N,
    "notes_created": M,
    "notes_updated": K,
    "ambiguous_cases_requiring_review": J,
    "rejected_low_quality": L
  }
}
```

## Consolidation Rules (R1-R8)

Apply these rules in order. Each VL output is evaluated against ALL applicable rules before a decision is made.

### R1: Same-Source Sequential Images → MERGE (highest priority)
If multiple VL outputs reference the same source file (`SOURCE_NOTE` matches), merge them into a single note. Use the highest-confidence output as the base; incorporate details from lower-confidence outputs that add unique information. Track all merged sources in `merged_from`.

### R2: Standalone Screenshot → KEEP AS STANDALONE
If a VL output has no other outputs sharing the same `SOURCE_NOTE` and the image is clearly a standalone screenshot (not part of a sequence), create it as an independent note. Use the VL's `CONSOLIDATION_REASON` to justify standalone status in the decision document.

### R3: Cross-Topic Overlap Detected → FLAG FOR HUMAN REVIEW
If the VL output's `CONSOLIDATION_CONFIDENCE` is "low" AND its topics field spans multiple distinct topic areas, flag as ambiguous. Do NOT merge into an existing note or create a new one — route to `ambiguous_cases` for human review.

### R4: Cross-Topic Overlap with Medium Confidence → PARTIAL MERGE
If `CONSOLIDATION_CONFIDENCE` is "medium" AND the VL output touches multiple topics, create a single note but list ALL relevant topics in the `topics` field. Add a comment in the decision document noting the cross-topic nature for future review.

### R5: Existing Topic Already Covers Concept → UPDATE INSTEAD OF CREATE
If the catalog context shows an existing note whose title closely matches the VL output's intended topic, and the concept described in the VL output is already covered by that note, produce an `update` action instead of a `create`. The orchestrator will append new content to the existing note.

### R6: Missing Metadata Fields → GRACEFUL FALLBACK
If any metadata field is missing from a VL output (e.g., no `CONSOLIDATION_CONFIDENCE` or `IMAGE_INDEX`), use sensible defaults:
- Missing `CONSOLIDATION_CONFIDENCE`: assume "medium" (do NOT reject)
- Missing `IMAGE_INDEX`: use 0 or the VL output's position in sequence
- Missing `SOURCE_NOTE`: mark as "unknown" and flag for review
The orchestrator's source mapping (not VL metadata) is the primary decision driver.

### R7: Low-Quality VL Output → DON'T POLLUTE MERGED NOTES
If a VL output has `CONSOLIDATION_CONFIDENCE` of "low" AND the content is vague, incomplete, or clearly hallucinated (e.g., missing key details from the image), mark it as rejected in `summary.rejected_low_quality`. Do NOT include low-quality content in merged notes from R1.

### R8: Orchestrator's Source Mapping Takes Precedence
When the orchestrator's source mapping conflicts with VL metadata (e.g., VL says `SOURCE_NOTE: A.png` but orchestrator knows it came from B.png), ALWAYS use the orchestrator's source mapping. VL metadata is a soft signal; orchestrator context is authoritative.

## Confidence Scoring Guidance
When producing the decision document, assess confidence based on:
- **high**: VL output is detailed, specific to the image content, and matches a clear concept
- **medium**: VL output captures most key points but may miss some details or have minor inaccuracies
- **low**: VL output is vague, generic, misses key visual elements, or contradicts itself

## Model Requirements
- **Model type**: Text-reasoning model (no vision required)
- **Assignment**: Config-driven — use the consolidation model from `defaults.consolidation_model` if configured, otherwise fall back to orchestrator's text model
- **Context**: This skill receives structured input (VL output + source mapping), not raw images — minimal context window pressure

## Processing Steps
1. Read the VL output file at `$VL_OUTPUT_FILE` and parse metadata lines before each `---NOTE_BOUNDARY---`
2. Apply R1-R8 rules in order to each VL output (or group of outputs)
3. For R5: compare against catalog context to detect existing topics that overlap with VL outputs
4. Produce the JSON decision document at `$CONSOLIDATE_OUTPUT_FILE`
5. Output includes all actions (create, update), ambiguous cases for human review, and a summary

## Constraints
- **DO NOT write any notes to disk** — produce only the decision document JSON
- **DO NOT modify VL output files** — they are read-only input
- **Treat all metadata fields as optional** — missing fields get sensible defaults (R6)
- **Source mapping is authoritative** — VL metadata is a soft signal, never overrides orchestrator context (R8)
