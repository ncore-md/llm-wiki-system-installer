# LLM Wiki Skills

**Agent-optimized skills for the LLM Wiki knowledge base system.**

These seven skills provide a complete pipeline: from first-time setup through source ingestion, knowledge querying, quality validation, security auditing, and periodic maintenance. Image analysis is handled by a dedicated vision-language skill injected as a subagent during ingestion.

---

## System Documentation (Cross-reference)

| Document | What it covers |
|---|---|
| [[system-overview]] | High-level architecture, two-layer structure (config + shared system), directory layout |
| [[entity-hierarchy-data-flow]] | Entity hierarchy, data flow between layers (config → AGENTS.md → tag routing → raw/compiled/catalog), frontmatter contract, note relationships |
| [[shared-infrastructure]] | Shared infrastructure (wiki_shared.py, wiki_tool.py), external tools (obsidian-cli, defuddle), design principles |
| [[ingest-pipeline]] | Complete ingest pipeline (Steps 0–9) with mandatory checklist, vault selection logic, image processing via VL subagent |
| [[query-maintenance]] | Query read path, maintenance pipeline (doctor → build → lint → source-lint), security audit before push |
| [[llm-wiki-audit]] | Security and compliance audit: secrets detection, broken wikilinks, orphaned notes, source coverage gaps |

---

## The Six Skills

| Skill | Purpose | Triggered By |
|---|---|---|
| **[ingest](llm-wiki-ingest/)** | Create & update wiki notes from raw sources (URL, file, pasted content) | User adds a source or asks to process unprocessed files |
| **[query](llm-wiki-query/)** | Answer questions from compiled knowledge (Wiki notes) | User asks something the wiki might know about |
| **[lint](llm-wiki-lint/)** | Validate frontmatter & schema before commits | Pre-commit gate, or user asks to check quality |
| **[maintain](llm-wiki-maintain/)** | Health checks: rebuild catalog, verify coverage, report issues | Periodic maintenance or before meaningful commits |
| **[vl](llm-wiki-vl/)** | Analyze images → produce wiki notes (subagent-only) | Automatically injected into ingest when image sources are found |
| **[setup](llm-wiki-setup/)** | Create `.llm-wiki-config/config.json` when missing | First-time run, no config found |
| **[audit](llm-wiki-audit/)** | Security & compliance: secrets, broken refs, orphans, coverage gaps | Before push to public repos; user request

---

## Skill Architecture

```
setup → config.json (enables all other skills)

ingest  ──┬──► Raw/Sources/ cleaned markdown
          ├──► Wiki/{Topics,Concepts,...}/ compiled notes (created or updated)
          └──► vl subagent (for image sources: analyze → notes)

query   ──► catalog search → read compiled Wiki notes → synthesize answer
lint    ──► wiki_tool.py lint + source-lint → report issues (schema quality)
maintain ─► doctor + build + lint + source-lint → health report (system state)
audit   ──► wiki_tool.py audit + security-scan → report issues (security & compliance)

Before commit: maintain validates everything
Before push to public repos: audit --mode public blocks on critical findings
```

### Dependencies

| Skill | Depends On | Notes |
|---|---|---|
| **setup** | `obsidian CLI` (vault discovery) | First skill to run. Produces config that all others need. |
| **ingest** | `vl` (for images), config from setup | Most complex — 10 steps with mandatory checklists. Orchestrator skill. |
| **vl** | None (subagent-only) | Never triggered directly by user. Injected into ingest subagents for image analysis. Outputs notes separated by `---NOTE_BOUNDARY---`. |
| **query** | `catalog.jsonl` (built by wiki_tool.py) | Read path. Prefers compiled Wiki notes over raw sources. |
| **lint** | `wiki_tool.py lint + source-lint` | Lightweight validation. Pre-commit gate. |
| **maintain** | `wiki_tool.py` (all commands) | Broader than lint. Includes catalog rebuilds and health checks. |
| **audit** | `wiki_tool.py` (audit + security-scan), audit-rules.json | Security & compliance. Runs before push to public repos, separate from lint (schema quality). |

---

## Deployment Model

Skills live in the wiki system at `.llm-wiki/Core/.agents/skills/`. They are **not** installed directly into project folders — a separate deployment skill (to be created) will copy them from the wiki root into each project's folder, making them available per-project.

This keeps skills as a **shared system** — one source of truth, deployed to wherever needed.

---

## Shared Infrastructure (Not Skills)

These are not skills themselves but support all of them:

| Component | Purpose |
|---|---|
| **`wiki_shared.py`** | Config discovery, model resolution (`resolve_model()`), VL discovery, shared utilities |
| **`wiki_tool.py`** | `build`, `lint`, `source-lint`, `search-catalog`, `source-scan`, `log`, **`security-scan`**, **`audit`** |
| **`.llm-wiki-config/config.json`** | Source of truth: vault declarations, permissions, model defaults |
| **`.llm-wiki-config/audit-rules.json`** | Configurable security scan patterns (secrets, paths to skip). Optional — uses built-in defaults if missing. |
| **Schema/** | Frontmatter rules (`frontmatter-schema.md`), lint checklist, naming conventions, cache |
| **`_templates/`** | Note templates per tag type (concept, entity, topic, project, log) |
| **`AGENTS.md` checklist** | Per-vault rules: `max_topics`, `required_sections`, **`tag_routing`**, etc. |

### Per-Vault Tag Routing (`tag_routing`)
Each vault defines its own tag → folder mapping in AGENTS.md's `---checklist---` block:

```yaml
---checklist---
tag_routing:
  Topics: topic
  Concepts: concept
  Snippets: snippet   # custom vault-specific tag!
---
```

Discovered by `_discover_tag_routing()` in priority order:
1. AGENTS.md `tag_routing` field (per-vault)
2. Directory Structure table in AGENTS.md
3. Wiki/ subdirectory scanning (fallback)

## Supporting Tools (External Skills)

Wiki skills depend on these Obsidian and web tools installed at `/Users/bernardoresende/.pi/skills/`:

| Tool | Purpose |
|---|---|
| **`obsidian-cli`** | Vault CRUD operations (read, write, search, properties) via Chrome DevTools Protocol. Used by ingest/query for all vault file operations. |
| **`defuddle`** | Web page content extraction — cleans HTML pages to readable markdown. Used by ingest when processing URLs. |
| **`json-canvas`** | Obsidian Canvas file creation/editing (nodes, edges, groups). Not directly used by wiki skills but available in the toolchain. |

---

## Quick Reference

| Operation | Command / Skill |
|---|---|
| First-time setup | `/llm-wiki-setup` or `skill: llm-wiki-setup` subagent |
| Ingest a source | `/llm-wiki-ingest <url>` or `skill: llm-wiki-ingest` |
| Query the wiki | `/llm-wiki-query <question>` or `skill: llm-wiki-query` |
| Validate before commit | `/llm-wiki-lint` or `skill: llm-wiki-lint` |
| Health check & rebuild | `/llm-wiki-maintain` or `skill: llm-wiki-maintain` |
| Security audit | `/llm-wiki-audit` or `skill: llm-wiki-audit`, or CLI: `wiki_tool.py audit --mode public|private` |
| Image analysis (internal) | Injected automatically via `skill: llm-wiki-vl` subagent |
