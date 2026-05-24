# Naming Conventions

Consistent naming makes the Wiki predictable for both humans and agents. Follow these rules when creating new notes or folders.

Related: [[Schema/frontmatter-schema.md]], [[AGENTS.md]]

## File Names

- Use **lowercase with hyphens** for file names: `knowledge-graphs.md`, not `Knowledge Graphs.md` or `knowledge_graphs.md`.
- Use **descriptive, noun-based names**: `graph-rag`, not `how-graph-rag-works`.
- Keep names **short but unambiguous** — 1–4 words typically.

## Folder Structure

| Folder | Content Type | Example |
|--------|-------------|---------|
| `Wiki/Topics/` | Broad subject areas | `knowledge-graphs.md`, `rag-systems.md` |
| `Wiki/Concepts/` | Discrete ideas, definitions, mechanisms | `graph-rag.md`, `knowledge-compilation.md` |
| `Wiki/Entities/` | People, organizations, tools, places | `wanderloots.md`, `obsidian.md` |
| `Wiki/Projects/` | Initiatives with scope and status | `llm-wiki.md`, `memory-systems.md` |
| `Wiki/Logs/` | Activity logs (single file) | `log.md` — always named exactly this |

## Wikilink Format

- Use **Title Case** in wikilinks: `[[Knowledge Graphs]]`, not `[[knowledge-graphs]]`.
- Wikilinks should use the **display name** of a note, not its file path.
- The display name is derived from the `Title` frontmatter field when present, otherwise from the file name.

## Note Titles (Front Matter)

- Use **Title Case** for note titles: `Graph RAG`, not `graph rag`.
- Keep titles **concise** — one line, no descriptions.

## Tags

- Use **lowercase with hyphens**: `knowledge-graphs`, not `Knowledge Graphs`.
- Each compiled note has exactly one type tag: `"topic"`, `"concept"`, `"entity"`, or `"project"`.
- Source notes always include the `"source"` tag.
