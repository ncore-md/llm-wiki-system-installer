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
import re
import sys
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Paths (relative to repo root)
# ---------------------------------------------------------------------------

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW_SOURCES_DIR = os.path.join(REPO_ROOT, "Raw", "Sources")
WIKI_DIR = os.path.join(REPO_ROOT, "Wiki")
SCHEMA_DIR = os.path.join(REPO_ROOT, "Schema")

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
    """Minimal YAML parser for the subset used in note frontmatter.

    Supports:
      - scalar strings (quoted and unquoted)
      - booleans (true/false)
      - integers
      - inline arrays ["a", "b"] and multi-line lists (one item per line starting with "- ")
    """
    props = {}
    current_key = None

    for line in text.split("\n"):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        # Array item continuation ("- value")
        if current_key and stripped.startswith("- "):
            val = stripped[2:].strip().strip('"').strip("'")
            if isinstance(props.get(current_key), list):
                props[current_key].append(val)
            continue

        # Key: value line
        m = re.match(r'^([A-Za-z_][\w-]*):\s*(.*)', line)
        if m:
            key = m.group(1)
            val_str = m.group(2).strip()

            if val_str == "":
                # Multi-line list starts next line(s)
                current_key = key
                props[key] = []
            elif val_str.startswith("[") and val_str.endswith("]"):
                # Inline array ["a", "b"]
                inner = val_str[1:-1]
                items = [i.strip().strip('"').strip("'") for i in inner.split(",") if i.strip()]
                props[key] = items
            elif val_str.lower() == "true":
                props[key] = True
            elif val_str.lower() == "false":
                props[key] = False
            else:
                try:
                    props[key] = int(val_str)
                except ValueError:
                    try:
                        props[key] = float(val_str)
                    except ValueError:
                        props[key] = val_str.strip('"').strip("'")

    return props


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


def get_raw_sources():
    """Return list of (rel_path, props) for all files in Raw/Sources/."""
    sources = []
    if not os.path.isdir(RAW_SOURCES_DIR):
        return sources
    for fname in sorted(os.listdir(RAW_SOURCES_DIR)):
        if not fname.endswith(".md"):
            continue
        fpath = os.path.join(RAW_SOURCES_DIR, fname)
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

    # Check required directories
    for d in [RAW_SOURCES_DIR, WIKI_DIR, SCHEMA_DIR]:
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


def cmd_build(args=None):
    """Generate catalog.jsonl, index.md, and per-folder indexes."""
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

        if tag not in ALLOWED_TAGS:
            errors.append(f"{rel_path}: invalid tag '{tag}' — allowed: {ALLOWED_TAGS}")

        # Check source_count matches sources array
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
                clean_src = re.sub(r'^\[\[|\]\]$', '', src).strip()
                if clean_src and not os.path.isfile(os.path.join(REPO_ROOT, clean_src)):
                    errors.append(f"{rel_path}: source '{src}' does not resolve")

        # Check compiled notes include ## Related and ## Sources sections
        full_path = os.path.join(REPO_ROOT, rel_path)
        try:
            with open(full_path, "r", encoding="utf-8") as f:
                body = f.read()
            if "## Related" not in body and "## Sources" not in body:
                # Check frontmatter tag to only flag compiled notes
                tags = props.get("tags", [])
                if isinstance(tags, list) and len(tags) > 0:
                    tag = tags[0]
                    if tag in ("topic", "concept", "entity", "project"):
                        errors.append(f"{rel_path}: compiled note missing ## Related and/or ## Sources sections")
        except FileNotFoundError:
            pass

        # Check dates
        for date_field in ("created", "updated"):
            val = props.get(date_field, "")
            if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(val)):
                errors.append(f"{rel_path}: '{date_field}' must be YYYY-MM-DD, got '{val}'")

    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  ✗ {e}")
        return False

    print(f"OK: lint passed ({len(wiki_notes)} notes checked).")
    return True


def cmd_source_scan(args):
    """List Raw sources and optionally update the manifest."""
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
                        clean_src = re.sub(r'^\[\[|\]\]$', '', src).strip()
                        if clean_src == rel_path:
                            covered = True
                            manifest[rel_path]["covered_by"].append(wpath)
                            break

                if covered:
                    manifest[rel_path]["processed"] = True
                    manifest[rel_path]["updated"] = today_str()

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
        if not re.match(r'^\d{4}-\d{2}-\d{2}$', str(created)):
            errors.append(f"{rel_path}: 'Created' or 'created' must be YYYY-MM-DD")

        tags = props.get("tags", [])
        if not isinstance(tags, list) or ("source" not in tags and "clippings" not in tags):
            errors.append(f"{rel_path}: missing 'source' or 'clippings' tag")

        # Check processed sources have coverage
        m = manifest.get(rel_path, {})
        if m.get("processed") and not m.get("covered_by"):
            errors.append(f"{rel_path}: marked processed but has no Wiki coverage")

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

    results = []
    if os.path.isfile(CATALOG_PATH):
        with open(CATALOG_PATH, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                entry = json.loads(line)
                # Search title, topics, and sources fields
                searchable = " ".join([
                    entry.get("title", ""),
                    " ".join(entry.get("topics", [])),
                    " ".join(entry.get("sources", [])),
                ]).lower()

                if query in searchable:
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
    "source-scan": cmd_source_scan,
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
