#!/usr/bin/env python3
"""LLM Wiki Tool — deterministic validation, indexing, and manifest management.

Required commands:
  doctor        Non-mutating health check for folders, Python version, catalog, manifest.
  build         Generate Wiki/catalog.jsonl, Wiki/index.md, and per-folder index files.
  lint          Validate compiled Wiki note frontmatter, allowed tags, source links, source_count.
  source-scan   List Raw sources and optionally update Schema/source-manifest.jsonl.
                --update: Update manifest entries for discovered sources.
                --accept-covered: Mark covered sources as processed in the manifest.
  source-lint   Validate Raw source frontmatter and coverage state (processed sources must have Wiki coverage).
  search-catalog --query "text"  Search compiled Wiki notes through the catalog.
  log --title "t" --details "d" Append a short entry to Wiki/Logs/log.md.

Uses only the Python standard library.
"""

import json
import os
import re as _re
import sys
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIKI_DIR = os.path.join(REPO_ROOT, "Wiki")
SCHEMA_DIR = os.path.join(REPO_ROOT, "Schema")

# Raw source directories — discovered from config (allows multiple dirs like Sources, Source, Ingest)
def get_raw_source_dirs():
    """Return list of absolute paths to Raw/ subdirectories containing source .md files.
    Reads from config cache; returns empty list if not configured."""
    try:
        cache_path = os.path.join(SCHEMA_DIR, ".llm-wiki-cache.json")
        with open(cache_path) as f:
            cache = json.load(f)
        dirs = cache.get("config", {}).get("raw_source_dirs")
        if dirs:
            return [os.path.join(REPO_ROOT, d) for d in dirs]
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []  # No configured dirs — discovery must run first
RAW_SOURCES_DIRS = get_raw_source_dirs()


def _ensure_raw_dirs_discovered():
    """Discover raw source directories from actual filesystem and update cache.
    Called when get_raw_source_dirs() returns empty — forces discovery from disk."""
    try:
        # Import wiki_shared for the actual directory scanning logic
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from wiki_shared import _discover_raw_source_dirs, get_cache_path
        cache_path = os.path.join(SCHEMA_DIR, ".llm-wiki-cache.json")
        dirs = _discover_raw_source_dirs(REPO_ROOT)
        if not dirs:
            return  # No raw directories found on disk
        with open(cache_path) as f:
            cache = json.load(f)
        config = cache.setdefault("config", {})
        config["raw_source_dirs"] = dirs
        with open(cache_path, "w") as f:
            json.dump(cache, f, indent=2)
    except (ImportError, FileNotFoundError, json.JSONDecodeError):
        pass

CATALOG_PATH = os.path.join(WIKI_DIR, "catalog.jsonl")
INDEX_PATH = os.path.join(WIKI_DIR, "index.md")
LOG_PATH = os.path.join(WIKI_DIR, "log.md")
MANIFEST_PATH = os.path.join(SCHEMA_DIR, "source-manifest.jsonl")

ALLOWED_TAGS = {"topic", "concept", "entity", "project", "log"}
FOLDER_FOR_TAG = {
    "topic": os.path.join(WIKI_DIR, "Topics"),
    "concept": os.path.join(WIKI_DIR, "Concepts"),
    "entity": os.path.join(WIKI_DIR, "Entities"),
    "project": os.path.join(WIKI_DIR, "Projects"),
}


# ---------------------------------------------------------------------------
# Helpers — frontmatter parsing (stdlib only)
# ---------------------------------------------------------------------------

def parse_frontmatter(text):
    """Parse YAML frontmatter from a markdown string. Returns (props_dict, body)."""
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            raw = parts[1].strip()
            props = yaml_parse(raw)
            body = "---".join(parts[2:]).lstrip("\n")
            return props, body
    return {}, text


def yaml_parse(text):
    """Parse YAML frontmatter. Uses custom parser for consistency.

    This is the same parser used by lint/build/source-scan. All content
    should be written with array format for tags/topics/sources to ensure
    consistency: tags:\n  - concept, topics:\n  - [[Topic]], sources:\n  - path.
    """
    props = {}
    current_key = None

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Array item continuation ("- value")
        if current_key and stripped.startswith("- "):
            val = _yaml_value(stripped[2:].strip())
            if current_key in props and isinstance(props[current_key], list):
                props[current_key].append(val)
            continue

        m = _re.match(r'^([A-Za-z_][\w-]*):\s*(.*)', line)
        if m:
            key = m.group(1)
            val_str = m.group(2).strip()

            if not val_str:
                # Multi-line list starts next line(s)
                current_key = key
                props[key] = []
            elif val_str.startswith("[") and val_str.endswith("]"):
                # Inline array ["a", "b"]
                inner = val_str[1:-1]
                items = [_yaml_value(i.strip()) for i in inner.split(",") if i.strip()]
                props[key] = items
            else:
                current_key = None  # reset on scalar/inline value
                props[key] = _yaml_value(val_str)

    return props


def _yaml_value(val_str):
    """Parse a YAML scalar value string."""
    val_str = val_str.strip().strip('"').strip("'")
    if val_str.lower() == "true": return True
    if val_str.lower() == "false": return False
    try: return int(val_str)
    except ValueError:
        pass
    try: return float(val_str)
    except ValueError:
        pass
    return val_str


def read_note(path):
    """Read a markdown file and return (frontmatter_dict, body_text)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        return parse_frontmatter(text)
    except FileNotFoundError:
        return {}, ""


def get_wiki_notes():
    """Return list of (rel_path, props) for all compiled Wiki notes.

    Excludes auto-generated index.md and Logs/log.md to prevent false positives in lint.
    """
    notes = []
    for tag, folder in FOLDER_FOR_TAG.items():
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith(".md"):
                continue
            # Skip auto-generated indexes and log files
            if fname in ("index.md", "log.md"):
                continue
            fpath = os.path.join(folder, fname)
            rel_path = os.path.relpath(fpath, REPO_ROOT)
            props, _body = read_note(fpath)
            notes.append((rel_path, props))
    return notes


# ─── Apostrophe Normalization ──────────────────────────────────────

_CURLY = '\u2019'  # U+2019 RIGHT SINGLE QUOTATION MARK (curly apostrophe)
_STRAIGHT = "'"    # U+0027 APOSTROPHE

def _normalize_curly_apostrophe(text):
    """Replace curly apostrophes with straight ones in text."""
    return text.replace(_CURLY, _STRAIGHT)


def normalize_raw_sources():
    """Normalize curly apostrophes in Raw/ filenames and frontmatter.

    Scans all .md files in configured Raw/ source directories. For any file
    with curly apostrophes (U+2019) in the filename, renames it to use straight
    apostrophes (U+0027) and updates frontmatter title/source fields to match.

    Returns:
        List of (old_rel_path, new_rel_path) tuples for renamed files.
    """
    renamed = []

    for raw_dir in RAW_SOURCES_DIRS:
        if not os.path.isdir(raw_dir):
            continue

        for fname in sorted(os.listdir(raw_dir)):
            if not fname.endswith(".md"):
                continue

            # Check if filename has curly apostrophes
            if _CURLY not in fname:
                continue

            fpath = os.path.join(raw_dir, fname)
            new_fname = _normalize_curly_apostrophe(fname)

            # Rename the file on disk
            new_fpath = os.path.join(raw_dir, new_fname)
            if fpath != new_fpath:
                os.rename(fpath, new_fpath)

            # Update frontmatter title and source references in the file
            with open(new_fpath, "r", encoding="utf-8") as f:
                content = f.read()

            # Update title in frontmatter (lines like: title: "..." or title: ...)
            def _fix_title(m):
                prefix = m.group(1)
                value = m.group(2)
                return f"{prefix}{_normalize_curly_apostrophe(value)}"
            content = _re.sub(r"(title:\s*[\"'])(.*?)([\"'])", _fix_title, content)

            # Update source: lines in frontmatter (YAML array items like:
            #   - Raw/Sources/... or - Raw/Source/...)
            def _fix_sources(m):
                prefix = m.group(1)
                value = m.group(2)
                return f"{prefix}{_normalize_curly_apostrophe(value)}"
            # Build regex to match source paths in any configured Raw/ directory
            raw_dirs = get_raw_source_dirs()
            if not raw_dirs:
                # No dirs in cache — try to discover from actual directories
                _ensure_raw_dirs_discovered()
                raw_dirs = get_raw_source_dirs()
            if raw_dirs:
                dir_names = [os.path.relpath(d, REPO_ROOT) for d in raw_dirs]
                pattern = r"(\-\s+)((?:" + "|".join(_re.escape(d) for d in dir_names) + r")/.*?)$"
                content = _re.sub(pattern, _fix_sources, content, flags=_re.MULTILINE)

            with open(new_fpath, "w", encoding="utf-8") as f:
                f.write(content)

            rel_old = os.path.relpath(fpath, REPO_ROOT)
            rel_new = os.path.relpath(new_fpath, REPO_ROOT)
            renamed.append((rel_old, rel_new))

    # Also normalize source paths in all compiled wiki notes
    _normalize_wiki_source_paths()

    return renamed


def _normalize_wiki_source_paths():
    """Normalize curly apostrophes in source paths within wiki note files."""
    fixed_count = 0

    for tag, wiki_folder in FOLDER_FOR_TAG.items():
        if not os.path.isdir(wiki_folder):
            continue

        for fname in sorted(os.listdir(wiki_folder)):
            if not fname.endswith(".md"):
                continue

            fpath = os.path.join(wiki_folder, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            # Check if file has any curly apostrophes in source paths
            if _CURLY not in content:
                continue

            # Normalize source paths in any configured Raw/ directory
            raw_dirs = get_raw_source_dirs()
            if not raw_dirs:
                _ensure_raw_dirs_discovered()
                raw_dirs = get_raw_source_dirs()
            if raw_dirs:
                dir_names = [os.path.relpath(d, REPO_ROOT) for d in raw_dirs]
                pattern = r"((?:" + "|".join(_re.escape(d) for d in dir_names) + r")/.*?)$"
                new_content = _re.sub(pattern, lambda m: _normalize_curly_apostrophe(m.group(0)), content, flags=_re.MULTILINE)
            else:
                new_content = content

            if new_content != content:
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                fixed_count += 1

    if fixed_count > 0:
        print(f"Normalized source paths in {fixed_count} wiki note(s).")


def get_raw_sources():
    """Return list of (rel_path, props) for all .md files in configured Raw/ source dirs."""
    sources = []
    for raw_dir in RAW_SOURCES_DIRS:
        if not os.path.isdir(raw_dir):
            continue
        for fname in sorted(os.listdir(raw_dir)):
            if not fname.endswith(".md"):
                continue
            fpath = os.path.join(raw_dir, fname)
            rel_path = os.path.relpath(fpath, REPO_ROOT)
            props, _body = read_note(fpath)
            sources.append((rel_path, props))
    return sources


def today_str():
    """Return current date as YYYY-MM-DD string."""
    return str(date.today())


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_doctor(args=None):
    """Non-mutating health check."""
    errors = []

    # Check Python version (3.8+)
    if sys.version_info < (3, 8):
        errors.append(f"Python {sys.version} is below minimum 3.8")

    # Check required directories (Raw source dirs + Wiki/Schema)
    for d in RAW_SOURCES_DIRS:
        if not os.path.isdir(d):
            errors.append(f"Missing source directory: {os.path.relpath(d, REPO_ROOT)}")
    for d in [WIKI_DIR, SCHEMA_DIR]:
        if not os.path.isdir(d):
            errors.append(f"Missing directory: {os.path.relpath(d, REPO_ROOT)}")

    # Check catalog exists
    if not os.path.isfile(CATALOG_PATH):
        errors.append(f"Catalog missing: {os.path.relpath(CATALOG_PATH, REPO_ROOT)}")

    # Check manifest exists
    if not os.path.isfile(MANIFEST_PATH):
        errors.append(f"Manifest missing: {os.path.relpath(MANIFEST_PATH, REPO_ROOT)}")

    # Count notes
    wiki_notes = get_wiki_notes()
    raw_sources = get_raw_sources()

    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ✗ {e}")
        return False

    print("OK: doctor passed")
    print(f"  Python {sys.version_info.major}.{sys.version_info.minor}")
    print(f"  Wiki notes: {len(wiki_notes)}")
    print(f"  Raw sources: {len(raw_sources)}")
    return True


def _fix_empty_sources():
    """Auto-fix notes with empty sources[] in frontmatter but source paths under ## Sources: body text.

    This corrects a common issue where notes are written with sources only in body sections
    (not YAML frontmatter), causing empty arrays that break source-scan and lint.
    """
    fixed = 0
    for tag, folder in FOLDER_FOR_TAG.items():
        if not os.path.isdir(folder):
            continue
        for fname in sorted(os.listdir(folder)):
            if not fname.endswith(".md") or fname in ("index.md",):
                continue
            fpath = os.path.join(folder, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()

            # Find frontmatter between --- delimiters (exactly 2 markers)
            if not content.startswith("---"):
                continue
            parts = content.split("---", 3)
            if len(parts) < 3:
                continue

            fm = parts[1]
            body = "---".join(parts[2:])  # rest after closing ---

            # Check if sources is empty in frontmatter (bare key with no value, or [])
            # Must NOT match sources: followed by list items (which means it already has values)
            src_match = _re.search(r'^sources:\s*(?:\[\])?$', fm, _re.MULTILINE)
            if not src_match:
                continue
            # Double-check: ensure no list items follow immediately (already has values)
            after_match = fm[src_match.end():]
            if _re.search(r'^\s*[-*]\s+', after_match):
                continue

            # Check for source paths under ## Sources: in body
            src_section = _re.search(r'^##\s+Sources\s*$', body, _re.MULTILINE)
            if not src_section:
                continue

            # Extract source paths from body section (lines starting with - or *)
            after_section = body[src_section.end():]
            body_sources = []
            for line in after_section.split("\n")[:20]:  # check first 20 lines
                stripped = line.strip()
                if _re.match(r'^[-*]\s+', stripped):
                    # Extract path from wikilink or plain text
                    cleaned = _re.sub(r'^[-*]\s+', '', stripped).strip()
                    # Remove wikilink brackets if present
                    cleaned = _re.sub(r'^\[\[|\]\]$', '', cleaned).strip()
                    if cleaned and not cleaned.startswith("http"):
                        body_sources.append(cleaned)

            if not body_sources:
                continue

            # Build new frontmatter with populated sources array and source_count
            old_fm = parts[1]
            # Replace only the bare "sources:" or "sources: []" line
            new_fm = _re.sub(
                r'^(sources:\s*(?:\[\])?\n)',
                f"sources:\n  - {body_sources[0]}"
                + "\n".join(f"  - {s}" for s in body_sources[1:]) + "\n",
                old_fm,
                flags=_re.MULTILINE
            )

            # Update source_count in frontmatter
            if _re.search(r'^source_count:\s*\d+', new_fm, _re.MULTILINE):
                new_fm = _re.sub(
                    r'^(source_count:\s*)\d+',
                    f"\\g<1>{len(body_sources)}",
                    new_fm,
                    flags=_re.MULTILINE
                )
            else:
                # Add source_count after sources array
                new_fm = _re.sub(
                    r'(sources:\s*\n(?:\s*- .+\n)+)',
                    f"\\g<1>source_count: {len(body_sources)}\n",
                    new_fm
                )

            # Write updated file
            parts[1] = new_fm
            with open(fpath, "w", encoding="utf-8") as f:
                f.write("---".join(parts))

            fixed += 1
    return fixed


def cmd_build(args=None):
    """Generate catalog.jsonl, index.md, and per-folder indexes."""
    # Auto-fix source paths: normalize curly apostrophes (U+2019 → U+0027)
    _normalize_wiki_source_paths()
    # Auto-fix empty sources arrays populated from body text sections
    fixed = _fix_empty_sources()
    if fixed:
        print(f"Auto-fixed {fixed} note(s) with empty sources[] — populated from body text.")

    wiki_notes = get_wiki_notes()

    # Build catalog
    with open(CATALOG_PATH, "w", encoding="utf-8") as f:
        for rel_path, props in wiki_notes:
            entry = {
                "path": rel_path,
                "title": props.get("Title", os.path.splitext(os.path.basename(rel_path))[0].replace("-", " ").title()),
                "tag": props.get("tags", [""])[0] if isinstance(props.get("tags"), list) else (props.get("tags", "") or ""),
                "topics": props.get("topics", []) if isinstance(props.get("topics"), list) else [],
                "sources": props.get("sources", []) if isinstance(props.get("sources"), list) else [],
                "source_count": props.get("source_count", 0),
                "updated": props.get("updated", today_str()),
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Build index.md
    with open(INDEX_PATH, "w", encoding="utf-8") as f:
        f.write("# Wiki Index\n\nRelated: [[AGENTS.md]], [[Schema/frontmatter-schema.md]]\n\n")
        for tag in ["topic", "concept", "entity", "project"]:
            folder_notes = [(p, pr) for p, pr in wiki_notes if (pr.get("tags", [""])[0] if isinstance(pr.get("tags"), list) else pr.get("tags", "")) == tag]
            # Fix irregular plurals
            plural = {"entity": "entities", "topic": "topics", "concept": "concepts", "project": "projects"}.get(tag, tag.title() + "s")
            f.write(f"## {plural[0].upper()}{plural[1:]}\n\n")
            if folder_notes:
                for rel_path, props in folder_notes:
                    title = props.get("Title", os.path.splitext(os.path.basename(rel_path))[0].replace("-", " ").title())
                    f.write(f"- [[{title}]] — {rel_path}\n")
            else:
                f.write("_No notes yet._\n")
            f.write("\n")

    # Build per-folder indexes
    for tag, folder in FOLDER_FOR_TAG.items():
        if not os.path.isdir(folder):
            continue
        idx_path = os.path.join(folder, "index.md")
        folder_notes = [(p, pr) for p, pr in wiki_notes if os.path.dirname(p).endswith(os.path.basename(folder))]
        # Fix irregular plurals
        plural = {"entity": "entities", "topic": "topics", "concept": "concepts", "project": "projects"}.get(tag, tag.title() + "s")
        with open(idx_path, "w", encoding="utf-8") as f:
            f.write(f"# {plural[0].upper()}{plural[1:]}\n\nRelated: [[Wiki/index.md]], [[AGENTS.md]]\n\n")
            if folder_notes:
                for rel_path, props in folder_notes:
                    title = props.get("Title", os.path.splitext(os.path.basename(rel_path))[0].replace("-", " ").title())
                    f.write(f"- [[{title}]]\n")
            else:
                f.write("_No notes yet._\n")

    print(f"OK: catalog.jsonl written with {len(wiki_notes)} entries.")
    return True


def cmd_lint(args=None):
    """Validate compiled Wiki note frontmatter."""
    wiki_notes = get_wiki_notes()

    # Parse vault rules (dynamic limits from AGENTS.md checklist section)
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from wiki_shared import parse_rules
        rules = parse_rules(REPO_ROOT)
    except Exception:
        # Fallback to hardcoded defaults if parsing fails (backward compat)
        rules = {"required_sections": ["## Related", "## Sources"],
                 "topics_required_for": ["concept", "entity"],
                 "max_topics": 5}

    max_topics = rules.get("max_topics")  # Optional — if absent, no limit enforced
    required_sections = rules.get("required_sections", ["## Related", "## Sources"])
    topics_required_for = rules.get("topics_required_for", ["concept", "entity"])
    allowed_tags_set = set(rules.get("allowed_tags", ["topic", "concept", "entity", "project"]))

    errors = []

    for rel_path, props in wiki_notes:
        # Check tag is valid and matches folder
        tags = props.get("tags", [])
        if not isinstance(tags, list):
            errors.append(f"{rel_path}: 'tags' must be an array")
            continue

        tag = tags[0] if tags else ""
        if not tag:
            errors.append(f"{rel_path}: missing tag")
            continue

        if tag not in allowed_tags_set:
            errors.append(f"{rel_path}: invalid tag '{tag}' — allowed: {sorted(allowed_tags_set)}")

        # Check source_count matches sources array (if required by rules)
        if rules.get("source_count_required", True):
            sources = props.get("sources", [])
        if not isinstance(sources, list):
            errors.append(f"{rel_path}: 'sources' must be an array")
        else:
            source_count = props.get("source_count", -1)
            if not isinstance(source_count, int):
                errors.append(f"{rel_path}: 'source_count' must be an integer")
            elif source_count != len(sources):
                errors.append(f"{rel_path}: source_count ({source_count}) ≠ sources length ({len(sources)})")

            # Check each source path exists (skip wikilink format)
            for src in sources:
                clean_src = _re.sub(r'^\[\[|\]\]$', '', src).strip()
                if clean_src and not os.path.isfile(os.path.join(REPO_ROOT, clean_src)):
                    errors.append(f"{rel_path}: source '{src}' does not resolve")

        # Check compiled notes include ## Related and ## Sources sections
        full_path = os.path.join(REPO_ROOT, rel_path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                body = f.read()
            # Check compiled notes include required sections from rules
            missing_sections = [s for s in required_sections if s not in body]
            if missing_sections:
                # Check frontmatter tag to only flag compiled notes
                tags = props.get("tags", [])
                if isinstance(tags, list) and len(tags) > 0:
                    tag = tags[0]
                    if tag in ("topic", "concept", "entity", "project"):
                        errors.append(f"{rel_path}: compiled note missing {', '.join(missing_sections)} sections")

            # Check topics consistency per tag (workflow Step 4: concept/entity must have ≥1 topic)
            tags = props.get("tags", [])
            if isinstance(tags, list) and len(tags) > 0:
                tag = tags[0]

                if tag in tuple(topics_required_for):
                    topics = props.get("topics", [])
                    if not isinstance(topics, list):
                        errors.append(f"{rel_path}: 'topics' must be an array (e.g., topics:\n  - [[Topic Name]])")
                        continue
                    # Validate: each topic must be a non-empty value (accepts [[Topic Name]] format)
                    has_valid_topic = False
                    for item in topics:
                        s = str(item).strip()
                        # Strip wikilink brackets for name extraction, but accept the format
                        s = _re.sub(r'^\[+|\]+$', '', s).strip()
                        if s:
                            has_valid_topic = True
                            break
                    if not has_valid_topic:
                        errors.append(f"{rel_path}: compiled note has empty 'topics' — must have ≥1 topic")



            # Check topics count ≤max_topics for concept/entity notes (optional — absent = no limit)
            if isinstance(tags, list) and len(tags) > 0:
                tag = tags[0]
                if max_topics is not None and tag in ("concept", "entity"):  # topics are broad overviews
                    topics = props.get("topics", [])
                    if isinstance(topics, list):
                        topic_count = len([t for t in topics if str(t).strip()])
                        if topic_count > max_topics:
                            errors.append(f"{rel_path}: {topic_count} topics (max {max_topics})")
        except FileNotFoundError:
            pass

        # Check dates
        for date_field in ("created", "updated"):
            val = props.get(date_field, "")
            if not _re.match(r'^\d{4}-\d{2}-\d{2}$', str(val)):
                errors.append(f"{rel_path}: '{date_field}' must be YYYY-MM-DD, got '{val}'")

    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ✗ {e}")
        return False

    print(f"OK: lint passed ({len(wiki_notes)} notes checked).")
    return True


# ---------------------------------------------------------------------------
# Fix frontmatter — auto-correct YAML type mismatches (scalar ↔ array)
# ---------------------------------------------------------------------------

# Schema field types: which fields must be arrays vs scalars per note category
SCHEMA_ARRAY_FIELDS = {
    "source": ["tags", "author", "ContentType", "sources"],
    "topic": ["tags", "topics", "notes", "aliases", "sources"],
    "concept": ["tags", "topics", "notes", "aliases", "sources"],
    "entity": ["tags", "topics", "notes", "aliases", "sources"],
    "project": ["tags", "notes", "topics", "aliases", "sources"],
    "log": [],  # log notes don't use frontmatter
}
SCHEMA_SCALAR_FIELDS = {
    "source": ["Title", "Author", "Reference", "Created", "Processed"],
    "topic": ["status", "created", "updated", "source_count"],
    "concept": ["status", "created", "updated", "source_count"],
    "entity": ["status", "created", "updated", "source_count"],
    "project": ["status", "created", "updated", "source_count"],
}

# Map singular tag → note category for determining schema context
TAG_TO_CATEGORY = {
    "source": "source",
    "topic": "topic",
    "concept": "concept",
    "entity": "entity",
    "project": "project",
}


def _get_yaml_module():
    """Import yaml module lazily to avoid dependency issues."""
    try:
        import yaml
        return yaml
    except ImportError:
        print("ERROR: PyYAML is required for fix-frontmatter. Install with: pip install pyyaml")
        return None


def _parse_frontmatter(filepath):
    """Parse frontmatter from a markdown file. Returns (props_dict, body_str) or None."""
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        if not content.startswith("---\n") and not content.startswith("---\r\n"):
            return None
        end_idx = content.find("---", 4)
        if end_idx == -1:
            return None
        fm_text = content[4:end_idx].strip()
        yaml = _get_yaml_module()
        if yaml is None:
            return None
        props = yaml.safe_load(fm_text)
        body = content[end_idx + 3:].strip()
        if not isinstance(props, dict):
            return None
        return props, body
    except Exception:
        return None


def _write_frontmatter(filepath, props):
    """Rewrite a file with corrected frontmatter using block-style YAML."""
    yaml = _get_yaml_module()
    if yaml is None:
        return False

    # Custom dump: force block-style lists and quote strings needing it
    class BlockDumper(yaml.Dumper):
        pass

    def _represent_list(dumper, data):
        return dumper.represent_sequence('tag:yaml.org,2002:seq', data, flow_style=False)

    def _represent_str(dumper, data):
        # Quote strings containing commas or YAML-special chars to prevent folding
        if any(c in data for c in [',', ': ', '#']):
            return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='"')
        return dumper.represent_scalar('tag:yaml.org,2002:str', data)

    BlockDumper.add_representer(list, _represent_list)
    BlockDumper.add_representer(str, _represent_str)

    fm_text = yaml.dump(props, Dumper=BlockDumper, default_flow_style=False, allow_unicode=True, sort_keys=False, width=10000)
    try:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        end_idx = content.find("---", 4)
        if end_idx == -1:
            return False
        body = content[end_idx + 3:]
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("---\n" + fm_text.rstrip() + "\n---\n" + body)
        return True
    except Exception:
        return False


def _fix_note_frontmatter(filepath, props):
    """Fix YAML type mismatches in a note's frontmatter.

    Checks each field against its expected schema type and converts:
      - scalar → list (e.g., tags: concept → [concept])
      - list → scalar where appropriate
    Returns True if any changes were made.
    """
    yaml = _get_yaml_module()
    if yaml is None:
        return False

    changed = False

    # Determine note category from tags field
    raw_tags = props.get("tags", [])
    if isinstance(raw_tags, str):
        raw_tags = [raw_tags]

    category = None
    for t in raw_tags:
        if isinstance(t, str) and t.strip() in TAG_TO_CATEGORY:
            category = TAG_TO_CATEGORY[t.strip()]
            break
    if not category:
        # Try to infer from filename or fields
        fname = os.path.basename(filepath)
        if "Source" in filepath:
            category = "source"

    # Determine which fields should be arrays vs scalars based on category
    if category:
        array_fields = SCHEMA_ARRAY_FIELDS.get(category, [])
        scalar_fields = SCHEMA_SCALAR_FIELDS.get(category, [])
    else:
        # Default: treat tags/topics/sources as arrays
        array_fields = ["tags", "topics", "sources"]
        scalar_fields = []

    for field in array_fields:
        val = props.get(field)
        if isinstance(val, str):
            # Scalar → list
            # For 'sources', always wrap as single-element (paths may contain commas)
            if field == "sources":
                props[field] = [val]
            else:
                # For tags/topics, split by comma
                if "," in val:
                    props[field] = [x.strip() for x in val.split(",") if x.strip()]
                else:
                    props[field] = [val]
            changed = True
        elif val is not None and isinstance(val, list):
            # Normalize: handle nested lists from PyYAML parsing wikilinks [[Topic]]
            new_list = []
            for item in val:
                if isinstance(item, list):
                    # PyYAML parsed [[Topic]] as ["Topic"] — reconstruct as wikilink
                    inner = item[0] if isinstance(item[0], str) else str(item[0])
                    new_list.append(f"[[{inner}]]")
                elif isinstance(item, dict):
                    new_list.append(str(item))
                else:
                    new_list.append(item)
            if len(new_list) != len(val):
                props[field] = new_list
                changed = True

    for field in scalar_fields:
        val = props.get(field)
        if isinstance(val, list) and len(val) == 1:
            # Single-element list → scalar
            props[field] = val[0]
            changed = True
        elif isinstance(val, list) and len(val) == 0:
            # Empty list → empty string for scalars
            props[field] = ""
            changed = True
        elif isinstance(val, list):
            # Multi-element list where scalar expected — keep as list
            pass  # Don't break things

    if changed:
        _write_frontmatter(filepath, props)

    return changed


def cmd_fix_frontmatter(args=None):
    """Auto-correct YAML type mismatches in all wiki note frontmatter.

    Fixes common issues like:
      - tags: concept (scalar) → [concept] (array)
      - topics: [[Topic]] inline vs multi-line array
    Returns True if any changes were made.
    """
    yaml = _get_yaml_module()
    if yaml is None:
        return False

    wiki_notes = get_wiki_notes()
    total_fixed = 0

    for rel_path, _props in wiki_notes:
        fpath = os.path.join(REPO_ROOT, rel_path)
        if not os.path.isfile(fpath):
            continue

        result = _parse_frontmatter(fpath)
        if result is None:
            continue

        props, body = result
        if _fix_note_frontmatter(fpath, props):
            total_fixed += 1
            print(f"  Fixed: {rel_path}")

    if total_fixed == 0:
        print("OK: All frontmatter types are correct. Nothing to fix.")
    else:
        print(f"Fixed {total_fixed} note(s). Run lint to verify.")

    return True


def cmd_normalize_apostrophes(args):
    """Normalize curly apostrophes in Raw/ filenames and frontmatter."""
    renamed = normalize_raw_sources()
    if not renamed:
        print("No files with curly apostrophes found.")
    else:
        for old, new in renamed:
            print(f"  {old} -> {new}")
        print(f"\nNormalized {len(renamed)} file(s).")

    # Update manifest if it exists (rename entries)
    if renamed and os.path.isfile(MANIFEST_PATH):
        manifest = {}
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    manifest[entry["path"]] = entry

        # Rebuild with new paths
        old_to_new = {old: new for old, new in renamed}
        updated_manifest = {}
        for path, entry in manifest.items():
            new_path = old_to_new.get(path, path)
            entry["path"] = new_path
            updated_manifest[new_path] = entry

        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            for entry in sorted(updated_manifest.values(), key=lambda e: e["path"]):
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        print("Manifest updated.")

    # Rebuild catalog to reflect new paths
    cmd_build([])

    return True


def cmd_source_scan(args):
    """List Raw sources and optionally update the manifest."""
    # Normalize curly apostrophes before scanning (prevents path mismatches)
    renamed = normalize_raw_sources()

    raw_sources = get_raw_sources()

    # Load existing manifest if it exists
    manifest = {}
    if os.path.isfile(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    manifest[entry["path"]] = entry

    update_manifest = "--update" in args
    accept_covered = "--accept-covered" in args

    for rel_path, props in raw_sources:
        if update_manifest and rel_path not in manifest:
            # New source — add to manifest (handle both title/Title)
            title = props.get("title", props.get("Title", "")) or os.path.splitext(os.path.basename(rel_path))[0].replace("-", " ").title()
            manifest[rel_path] = {
                "path": rel_path,
                "title": title,
                "processed": props.get("Processed", False),
                "covered_by": [],
                "updated": today_str(),
            }

    # Fix 1a: Deduplicate — merge old (curly apostrophe) manifest entries into new ones
    if renamed and update_manifest:
        old_to_new = {old: new for old, new in renamed}
    else:
        old_to_new = {}

    # Fix 1b: General stale-path cleanup — remove manifest entries whose paths don't exist on disk
    # This catches duplicates where the file was already normalized but old manifest entries remain.
    if update_manifest:
        to_remove = []
        for path, entry in list(manifest.items()):
            full_path = os.path.join(REPO_ROOT, path)
            if not os.path.isfile(full_path):
                # Path doesn't exist on disk — check if it's a renamed duplicate
                new_path = old_to_new.get(path)
                if new_path and new_path in manifest:
                    # Merge old entry into new-path entry
                    if not manifest[new_path].get("processed") and entry.get("processed"):
                        manifest[new_path]["processed"] = entry.get("processed", False)
                    if not manifest[new_path].get("covered_by") and entry.get("covered_by"):
                        manifest[new_path]["covered_by"] = list(entry["covered_by"])
                    to_remove.append(path)
                else:
                    # Truly stale entry — remove it
                    to_remove.append(path)
        for path in to_remove:
            del manifest[path]

    # If --accept-covered, mark sources that have Wiki notes as processed and covered
    if accept_covered:
        wiki_notes = get_wiki_notes()
        for rel_path, props in raw_sources:
            if manifest.get(rel_path):
                # Check if any wiki note references this source
                covered = False
                for wpath, wprops in wiki_notes:
                    sources_list = wprops.get("sources", []) if isinstance(wprops.get("sources"), list) else []
                    for src in sources_list:
                        clean_src = _re.sub(r'^\[\[|\]\]$', '', src).strip()
                        if clean_src == rel_path and wpath not in manifest[rel_path]["covered_by"]:
                            covered = True
                            manifest[rel_path]["covered_by"].append(wpath)
                            break

                if covered:
                    manifest[rel_path]["processed"] = True
                    manifest[rel_path]["updated"] = today_str()

    # Fix 2a: Validate covered_by entries — remove references to deleted/moved wiki notes
    if accept_covered:
        for rel_path, entry in manifest.items():
            valid_covered = []
            stale_count = 0
            for wpath in entry.get("covered_by", []):
                full_wiki_path = os.path.join(REPO_ROOT, wpath)
                if os.path.isfile(full_wiki_path):
                    valid_covered.append(wpath)
                else:
                    stale_count += 1
            if stale_count > 0 and valid_covered != entry.get("covered_by", []):
                # Only update if something changed
                entry["covered_by"] = valid_covered
            # If all coverage was stale, mark as unprocessed (lint will catch this)
            if not entry.get("covered_by"):
                entry["processed"] = False

    # Write manifest back if updated
    if update_manifest or accept_covered:
        with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
            for entry in sorted(manifest.values(), key=lambda e: e["path"]):
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    # Print summary
    print(f"Raw sources: {len(raw_sources)}")
    for rel_path, props in raw_sources:
        m = manifest.get(rel_path, {})
        status = "processed" if m.get("processed") else "unprocessed"
        covered_by = len(m.get("covered_by", []))
        print(f"  {'✓' if m.get('processed') else '·'} {rel_path} ({status}, {covered_by} wiki notes)")

    return True


def cmd_source_lint(args=None):
    """Validate Raw source frontmatter and coverage state."""
    raw_sources = get_raw_sources()

    # Load manifest
    manifest = {}
    if os.path.isfile(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    manifest[entry["path"]] = entry

    errors = []

    for rel_path, props in raw_sources:
        # Check required fields (case-insensitive: user sources may use title/Title, source/Reference)
        if not props.get("Title") and not props.get("title"):
            errors.append(f"{rel_path}: missing 'Title' or 'title'")
        if not props.get("Reference") and not props.get("source"):
            errors.append(f"{rel_path}: missing 'Reference' or 'source'")

        created = props.get("Created", "") or props.get("created", "")
        if not _re.match(r'^\d{4}-\d{2}-\d{2}$', str(created)):
            errors.append(f"{rel_path}: 'Created' or 'created' must be YYYY-MM-DD")

        tags = props.get("tags", [])
        if not isinstance(tags, list) or len(tags) == 0:
            errors.append(f"{rel_path}: 'tags' must be a non-empty list")
        else:
            # Source notes must use tag [source] (per original design)
            expected_tags = _re.findall(r"\[([^]]+)\]", str(tags))
            # Also handle tags that were written with quotes
            clean_tags = [t.strip().strip('"').strip("'") for t in tags]
            if clean_tags and clean_tags[0] != "source":
                errors.append(f"{rel_path}: source tag must be [source], found [{clean_tags[0]}]")

        # Validate ContentType field (per vault's allowed_content_types)
        ct = props.get("ContentType") or props.get("contentType")
        if not ct:
            errors.append(f"{rel_path}: missing 'ContentType' field")
        else:
            # Get allowed content types from vault rules
            try:
                sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
                from wiki_shared import _discover_content_types
            except ImportError:
                allowed_ct = []  # no restriction if import fails
            else:
                allowed_ct = _discover_content_types(REPO_ROOT)
            # ContentType can be a string or a YAML list ["video"]
            if isinstance(ct, list):
                ct_val = str(ct[0]).strip().lower() if ct else ""
            elif isinstance(ct, str):
                ct_val = ct.strip().lower()
            else:
                ct_val = str(ct).strip().lower()
            if not ct_val:
                errors.append(f"{rel_path}: 'ContentType' must be a non-empty value")
            elif allowed_ct and ct_val not in allowed_ct:
                errors.append(f"{rel_path}: invalid ContentType '{ct}' — allowed: {allowed_ct}")

        # Check processed sources have coverage
        m = manifest.get(rel_path, {})
        if m.get("processed") and not m.get("covered_by"):
            errors.append(f"{rel_path}: marked processed but has no Wiki coverage")

        # Fix 3a: Validate that covered_by entries actually exist on disk
        if m.get("processed") and m.get("covered_by"):
            stale_entries = []
            for wpath in m["covered_by"]:
                if not os.path.isfile(os.path.join(REPO_ROOT, wpath)):
                    stale_entries.append(wpath)
            if len(stale_entries) == len(m["covered_by"]):
                # ALL covered notes are gone — source is effectively unprocessed
                errors.append(f"{rel_path}: marked processed but all {len(stale_entries)} covered notes are missing")
            elif stale_entries:
                # Some entries exist, some don't — report but allow (will be cleaned by --accept-covered)
                errors.append(f"{rel_path}: marked processed but {len(stale_entries)} covered notes missing: {', '.join(s for s in stale_entries)}")

    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ✗ {e}")
        return False

    processed = sum(1 for m in manifest.values() if m.get("processed"))
    print(f"OK: source-lint passed ({len(raw_sources)} sources, {processed} processed).")
    return True


def cmd_source_delta(args=None):
    """Show Raw sources not in manifest and vice versa — the actionable delta."""
    raw_sources = get_raw_sources()

    # Load manifest
    manifest = {}
    if os.path.isfile(MANIFEST_PATH):
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    entry = json.loads(line)
                    manifest[entry["path"]] = entry

    new_sources = []
    missing_in_raw = []

    # Find Raw sources not in manifest (actionable delta)
    for rel_path, _props in raw_sources:
        if rel_path not in manifest:
            new_sources.append(rel_path)

    # Find manifest entries with no Raw source (cleanup candidates)
    for mpath in sorted(manifest.keys()):
        if not os.path.isfile(os.path.join(REPO_ROOT, mpath)):
            missing_in_raw.append(mpath)

    if new_sources and not missing_in_raw:
        print(f"{len(new_sources)} actionable delta(s) — new Raw sources not in manifest:")
        for s in new_sources:
            print(f"  + {s}")
    elif missing_in_raw and not new_sources:
        print(f"{len(missing_in_raw)} manifest entries with no Raw source (cleanup candidates):")
        for s in missing_in_raw:
            print(f"  - {s}")
    elif new_sources and missing_in_raw:
        print(f"{len(new_sources)} actionable delta(s), {len(missing_in_raw)} cleanup candidates:")
        for s in new_sources:
            print(f"  + {s}")
        for s in missing_in_raw:
            print(f"  - {s}")
    else:
        print("OK: no actionable delta — all Raw sources are in manifest.")

    return True


def cmd_search_catalog(args):
    """Search compiled Wiki notes through the catalog."""
    query_idx = args.index("--query") if "--query" in args else -1
    if query_idx < 0 or query_idx + 1 >= len(args):
        print("ERROR: usage: wiki_tool.py search-catalog --query \"text\"")
        return False

    query = args[query_idx + 1].lower()

    # Split into individual search terms for better recall
    query_terms = set(query.split())

    results = []
    if os.path.isfile(CATALOG_PATH):
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                # Search title, topics, tags, and sources fields
                searchable = " ".join([
                    entry.get("title", ""),
                    " ".join(entry.get("topics", [])),
                    entry.get("tag", ""),
                    " ".join(entry.get("sources", [])),
                ]).lower()

                # Match if any query term appears in searchable fields (not just exact phrase)
                if any(term in searchable for term in query_terms):
                    results.append(entry)

    print(f"Search '{args[query_idx + 1]}' — {len(results)} results:")
    for entry in results:
        print(f"  [{entry.get('tag', '?')}] {entry['title']} — {entry['path']}")

    return True


def cmd_log(args):
    """Append a short entry to Wiki/Logs/log.md."""
    title_idx = args.index("--title") if "--title" in args else -1
    details_idx = args.index("--details") if "--details" in args else -1

    if title_idx < 0 or details_idx < 0:
        print('ERROR: usage: wiki_tool.py log --title "t" --details "d"')
        return False

    title = args[title_idx + 1] if title_idx + 1 < len(args) else ""
    details = args[details_idx + 1] if details_idx + 1 < len(args) else ""

    log_path = LOG_PATH
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    entry = f"\n## [{timestamp}] {title}\n\n{details}\n"

    if os.path.isfile(log_path):
        with open(log_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Check if file has a header already
        if not content.strip().startswith("#"):
            with open(log_path, "w", encoding="utf-8") as f:
                f.write("# Wiki Activity Log\n" + entry)
        else:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(entry)
    else:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write("# Wiki Activity Log\n" + entry)

    print(f"OK: log entry added — [{timestamp}] {title}")
    return True


# ---------------------------------------------------------------------------
# Main dispatch
# ---------------------------------------------------------------------------

COMMANDS = {
    "doctor": cmd_doctor,
    "build": cmd_build,
    "lint": cmd_lint,
    "fix-frontmatter": cmd_fix_frontmatter,
    "source-scan": cmd_source_scan,
    "normalize-apostrophes": cmd_normalize_apostrophes,
    "source-lint": cmd_source_lint,
    "source-delta": cmd_source_delta,
    "search-catalog": cmd_search_catalog,
    "log": cmd_log,
}


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 wiki_tool.py <command> [args]")
        print(f"Commands: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    cmd = sys.argv[1]
    if cmd not in COMMANDS:
        print(f"Unknown command: {cmd}")
        print(f"Available commands: {', '.join(COMMANDS.keys())}")
        sys.exit(1)

    success = COMMANDS[cmd](sys.argv[2:])
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
