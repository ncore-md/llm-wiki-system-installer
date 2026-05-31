#!/usr/bin/env python3
"""Shared utilities for all llm-wiki skills.

This module provides:
- Per-project cache management (Schema/.llm-wiki-cache.json)
- VL model discovery with shared caching
- Vault validation and Raw folder detection
- Default/override configuration for tasks

All llm-wiki skills should import from here instead of duplicating logic.
"""

import json
import os
import re as _re
import sys
from datetime import datetime as _datetime
from pathlib import Path


# ─── Cache File Paths ───────────────────────────────────────────────

def get_cache_path(wiki_root=None):
    """Get the shared cache file path for this wiki project.

    The cache lives at WikiRoot/Schema/.llm-wiki-cache.json (per-project,
    not in ~/.pi/cache). This allows all skills to share state and for
    the cache to travel with the wiki repo.

    Args:
        wiki_root: Path to the wiki root directory. If None, tries to detect
                   from current working directory or parent directories.

    Returns:
        Path object pointing to the cache file.
    """
    if wiki_root is None:
        # Try to detect from current working directory
        cwd = Path.cwd()

        # If we're in a wiki root (has Schema/ and Wiki/), use it
        if (cwd / "Schema").exists() and (cwd / "Wiki").exists():
            wiki_root = cwd

        # Otherwise, walk up to find a directory with Schema/ and Wiki/
        if wiki_root is None:
            for parent in list(cwd.parents)[:5]:  # Check up to 5 levels deep (list() for Python 3.9 compatibility)
                schema_dir = parent / "Schema"
                wiki_dir = parent / "Wiki"
                if schema_dir.exists() and wiki_dir.exists():
                    wiki_root = parent
                    break

        # Also check immediate children (e.g., wiki root is <parent>/Core/)
        if wiki_root is None:
            try:
                for child in cwd.iterdir():
                    if child.is_dir() and (child / "Schema").exists() and (child / "Wiki").exists():
                        wiki_root = child
                        break
            except PermissionError:
                pass

    if wiki_root is None:
        print("ERROR: Could not detect wiki root. Pass wiki_root= or run from a wiki directory.", file=sys.stderr)
        sys.exit(1)

    return Path(wiki_root) / "Schema" / ".llm-wiki-cache.json"


def get_schema_path(wiki_root=None):
    """Get the Schema directory path."""
    if wiki_root is None:
        # Use same detection logic as get_cache_path but return Schema dir
        cwd = Path.cwd()
        if (cwd / "Schema").exists():
            return cwd / "Schema"
    wiki_path = get_cache_path(wiki_root)
    return wiki_path.parent


def load_cache(cache_path=None):
    """Load the shared cache, creating defaults if missing.

    Args:
        cache_path: Optional explicit path to the cache file. If None,
                    auto-detects from wiki root.

    Returns:
        dict with cache contents (may be freshly initialized).
    """
    if cache_path is None:
        cache_path = get_cache_path()

    defaults = _get_default_schema()

    if not cache_path.exists():
        # Create fresh cache with defaults
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        _write_cache(cache_path, defaults)
        return json.loads(json.dumps(defaults))  # Deep copy

    try:
        with open(cache_path) as f:
            cache = json.load(f)

        # Ensure all default keys exist (forward compatibility)
        for key, val in defaults.items():
            if key not in cache:
                cache[key] = json.loads(json.dumps(val))  # Deep copy

        return cache
    except (json.JSONDecodeError, IOError) as e:
        print(f"WARNING: Cache file corrupted ({e}), recreating with defaults", file=sys.stderr)
        _write_cache(cache_path, defaults)
        return json.loads(json.dumps(defaults))


def save_cache(data, cache_path=None):
    """Save data to the shared cache.

    Args:
        data: dict with cache contents to save.
        cache_path: Optional explicit path to the cache file.

    Returns:
        Path where data was saved.
    """
    if cache_path is None:
        cache_path = get_cache_path()

    _write_cache(cache_path, data)
    return cache_path


def _get_default_schema():
    """Return the default schema with all expected keys."""
    return {
        "schema_version": 1,
        "updated_at": None,

        # ── Wiki Config (discovered from AGENTS.md + directory scan) ─
        # This section is populated by wiki_discover.py and read by skills.
        # It contains persistent project settings — not runtime state.
        "config": {
            "wiki_name": None,           # Display name of this wiki project
            "tag_routing": {},           # {"topic": "Wiki/Topics", ...} — compiled note routing
            "allowed_compiled_tags": [], # Tags allowed in Wiki notes (first tag = folder)
            "allowed_source_tags": ["*"],  # Star = any non-empty tag list allowed (source-lint: len(tags) > 0)
            "compiled_required_fields": [],  # Required YAML fields for compiled notes
            "source_required_fields": [],      # Required YAML fields for source notes
            "paths": {
                "templates_dir": None,   # e.g., "_templates"
                "wiki_dir": None,        # e.g., "Wiki"
                "schema_dir": None,      # e.g., "Schema"
            },
            "vaults": {},                # {"Core": {path, permissions: [...], has_raw}}
            "discovered_at": None,       # ISO timestamp when last discovered
            "stale": False,              # Set True if AGENTS.md changed since discovery
        },

        # ── Shared Defaults (user-configurable) ─────────────────────
        "defaults": {
            # VL model defaults for image ingest tasks
            "vl_provider": None,       # e.g., "omlx", "openai"
            "vl_model_id": None,       # e.g., "qwen3.6-35b-a3b-mlx-vl-oQ4-FP16"
            "vl_base_url": None,       # e.g., "http://localhost:8000/v1"

            # Text model defaults for note generation tasks
            "text_provider": None,     # e.g., "omlx"
            "text_model_id": None,     # e.g., "qwen3.6-35b-a3b-oQ6"

            # Default vault for operations
            "default_vault": None,     # e.g., "Core"

            # Agent vision capability
            "agent_has_vision": False,  # Whether pi's current model has native vision
        },

        # ── Per-Vault Configurations ────────────────────────────────
        "vaults": {},

        # ── Per-Vault VL Discovery Results (updated by discovery) ───
        "vl_discovery": {},

        # ── Per-Task Overrides (user-configurable) �──────────────────
        "task_overrides": {

            # Image ingest: which VL model to use (overrides defaults)
            "image_ingest": {
                "vl_provider": None,
                "vl_model_id": None,
            },

            # Video analysis: which VL model to use (overrides defaults)
            "video_analysis": {
                "vl_provider": None,
                "vl_model_id": None,
            },

            # Note generation: which text model to use (overrides defaults)
            "note_generation": {
                "text_provider": None,
                "text_model_id": None,
            },

        },

    }


def _write_cache(cache_path, data):
    """Write cache data to disk with metadata."""
    cache_path.parent.mkdir(parents=True, exist_ok=True)

    if data.get("updated_at") is None:
        import datetime
        data["updated_at"] = datetime.datetime.now().isoformat()

    with open(cache_path, "w") as f:
        json.dump(data, f, indent=2)


# ─── VL Discovery (shared across all skills) ──────────────────────

def discover_vl_models(cache_path=None, force=False):
    """Discover vision-capable models and update the shared cache.

    Reads ~/.pi/agent/models.json to find all VL-capable models across
    registered providers. Checks if pi's current model has native vision.

    Args:
        cache_path: Optional explicit path to the shared cache file.
        force: If True, re-run discovery even if cache is fresh.

    Returns:
        dict with keys: agent_has_vision, provider, model_id, base_url.
    """
    if cache_path is None:
        cache_path = get_cache_path()

    cache = load_cache(cache_path)

    # Check if we should skip discovery (cache valid, not forcing)
    if not force:
        defaults = cache.get("defaults", {})
        agent_vision = defaults.get("agent_has_vision")

        # If discovery was already run and results are valid, return them
        if agent_vision is not None:
            vl_disc = cache.get("vl_discovery", {})

            # Case 1: Agent has native vision — no external VL needed
            if agent_vision and not vl_disc.get("provider"):
                return {
                    "agent_has_vision": True,
                    "provider": None,
                    "model_id": None,
                    "base_url": None,
                }

            # Case 2: Local VL model was discovered — check validity
            if vl_disc.get("provider") and vl_disc.get("model_id"):
                base_url = vl_disc.get("base_url", "")
                if base_url:  # Non-empty baseUrl means cache is valid
                    return {
                        "agent_has_vision": False,
                        "provider": vl_disc["provider"],
                        "model_id": vl_disc["model_id"],
                        "base_url": base_url,
                    }

    # Need to run discovery — read models.json
    models_file = os.path.expanduser("~/.pi/agent/models.json")
    if not os.path.exists(models_file):
        result = {
            "agent_has_vision": False,
            "provider": None,
            "model_id": None,
            "base_url": None,
        }

        # Update cache even on failure (so we don't retry endlessly)
        _update_discovery_cache(cache, result)
        return result

    with open(models_file) as f:
        registry = json.load(f)

    settings_file = os.path.expanduser("~/.pi/agent/settings.json")
    default_provider = "omlx"

    if os.path.exists(settings_file):
        with open(settings_file) as f:
            settings = json.load(f)
        default_provider = settings.get("defaultProvider", "omlx")

    # Discover ALL VL-capable models across all registered providers
    vl_models = []  # list of {provider, model_id, base_url}

    for provider_key, provider_data in registry.get("providers", {}).items():
        base_url = provider_data.get("baseUrl")

        # Check main models list for VL models
        seen_ids = set()
        for model_entry in provider_data.get("models", []):
            mid = model_entry.get("id", "")
            mid_lower = mid.lower()

            if mid_lower in seen_ids:
                continue

            input_types = list(model_entry.get("input", ["text"]))
            if "image" in input_types:
                seen_ids.add(mid_lower)
                vl_models.append({
                    "provider": provider_key,
                    "model_id": mid,
                    "base_url": base_url,
                })

        # Check modelOverrides for VL models not in main list
        for override_key, override_val in provider_data.get("modelOverrides", {}).items():
            input_types = list(override_val.get("input", ["text"]))
            if "image" in input_types:
                mid_lower = override_key.lower()
                if mid_lower not in seen_ids:
                    seen_ids.add(mid_lower)
                    vl_models.append({
                        "provider": provider_key,
                        "model_id": override_key,
                        "base_url": base_url,
                    })

    # Check if pi's CURRENT model has vision support
    current_model_vision = False
    known_current_models = ["qwen3.6-35b-a3b-oQ6", "qwen3.6-35b-a3b-bf16-mlx"]

    for provider_key, provider_data in registry.get("providers", {}).items():
        for model_entry in provider_data.get("models", []):
            mid = model_entry.get("id", "").lower()
            for known in known_current_models:
                if mid.replace("-", "") == known.replace("-", "") and "image" in model_entry.get("input", []):
                    current_model_vision = True

    # Build result
    defaults = cache.get("defaults", {})
    if current_model_vision:
        # Case 1: Agent's current model has vision — no external VL needed
        result = {
            "agent_has_vision": True,
            "provider": None,
            "model_id": None,
            "base_url": None,
        }
    elif vl_models:
        # Case 2: Local VL model found — prefer omlx, then first available
        chosen = None
        for m in vl_models:
            if m["provider"] == "omlx":
                chosen = m
                break
        if not chosen:
            chosen = vl_models[0]

        result = {
            "agent_has_vision": False,
            "provider": chosen["provider"],
            "model_id": chosen["model_id"],
            "base_url": chosen.get("base_url"),
        }
    else:
        # Case 3: Nothing found
        result = {
            "agent_has_vision": False,
            "provider": None,
            "model_id": None,
            "base_url": None,
        }

    _update_discovery_cache(cache, result)
    return result


def _update_discovery_cache(cache, result):
    """Update the vl_discovery section of cache with discovery results."""
    if "vl_discovery" not in cache:
        cache["vl_discovery"] = {}

    if result.get("agent_has_vision"):
        # Agent has native vision — clear external VL info
        cache["vl_discovery"] = {}

    else:
        # Store discovery results
        if result.get("provider"):
            cache["vl_discovery"] = {
                "provider": result["provider"],
                "model_id": result["model_id"],
                "base_url": result.get("base_url"),
            }

    # Update defaults.agent_has_vision if it was None (first run)
    if cache.get("defaults", {}).get("agent_has_vision") is None:
        cache.setdefault("defaults", {})["agent_has_vision"] = result.get("agent_has_vision", False)

    save_cache(cache)


# ─── Project Config Discovery (.llm-wiki-config/) ────────────────

_PROJECT_CONFIG_DIR = ".llm-wiki-config"
_PROJECT_CONFIG_FILE = "config.json"


def find_project_config(wiki_root=None):
    """Find the project config directory by walking up from wiki root.

    Searches for .llm-wiki-config/ starting at the wiki root, then each parent.

    Args:
        wiki_root: Path to the wiki root. Auto-detected if None.

    Returns:
        Path to .llm-wiki-config/ or None if not found.
    """
    if wiki_root is None:
        wiki_root = _detect_wiki_root()

    parents_list = list(Path(wiki_root).parents)[:5]
    for parent in [Path(wiki_root)] + parents_list:
        config_dir = parent / _PROJECT_CONFIG_DIR
        if config_dir.is_dir():
            return config_dir
    return None


def load_project_config(wiki_root=None):
    """Load and validate the project config file.

    Reads .llm-wiki-config/config.json from the wiki's project root.

    Args:
        wiki_root: Path to the wiki root. Auto-detected if None.

    Returns:
        dict with config contents, or None if not found/invalid.
    """
    config_dir = find_project_config(wiki_root)
    if not config_dir:
        return None

    config_file = config_dir / _PROJECT_CONFIG_FILE
    if not config_file.exists():
        return None

    try:
        with open(config_file) as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        print(f"WARNING: Project config invalid ({e}), skipping.", file=sys.stderr)
        return None

    # Validate required keys
    if not isinstance(data, dict):
        print("WARNING: Project config is not a JSON object.", file=sys.stderr)
        return None
    if "vaults" not in data:
        print("WARNING: Project config missing 'vaults' key.", file=sys.stderr)
        return None
    if not isinstance(data["vaults"], dict):
        print("WARNING: Project config 'vaults' must be a mapping.", file=sys.stderr)
        return None
    if not data["vaults"]:
        print("WARNING: Project config 'vaults' is empty.", file=sys.stderr)
        return None

    # Validate each vault entry
    for vname, vinfo in data["vaults"].items():
        if not isinstance(vinfo, dict):
            print(f"WARNING: Vault '{vname}' config must be a mapping.", file=sys.stderr)
            return None
        perms = vinfo.get("permissions", [])
        valid_perms = {"read", "write", "ingest", "maintain"}
        if not isinstance(perms, list) or not all(p in valid_perms for p in perms):
            print(
                f"WARNING: Vault '{vname}' has invalid permissions {perms}. "
                f"Must be list of: read, write, ingest, maintain.",
                file=sys.stderr,
            )
            return None

    return data


def get_project_config_path(wiki_root=None):
    """Get the path to .llm-wiki-config/config.json.

    Args:
        wiki_root: Path to the wiki root. Auto-detected if None.

    Returns:
        Path object or None.
    """
    config_dir = find_project_config(wiki_root)
    if not config_dir:
        return None
    return config_dir / _PROJECT_CONFIG_FILE


# ─── Wiki Config Discovery (AGENTS.md + directory scan) ─────────────


def discover_config(wiki_root=None, force=False):
    """Discover wiki structure from AGENTS.md and directory layout.

    Populates the `config` section of the shared cache with discovered
    settings (tag routing, allowed tags, paths). Skips if config is fresh.

    Args:
        wiki_root: Path to the wiki root (where AGENTS.md lives). Auto-detected if None.
        force: If True, re-discover even if cache says not stale. Default False.

    Returns:
        dict with the discovered config section (same structure as cache["config"]).
    """
    if wiki_root is None:
        wiki_root = _detect_wiki_root()

    cache_path = get_cache_path(wiki_root)
    cache = load_cache(cache_path)

    # Check staleness — skip if config is fresh and not forcing
    config = cache.setdefault("config", {})
    discovered_at = config.get("discovered_at")

    if not force and discovered_at:
        # Check if AGENTS.md has changed since last discovery
        agents_path = os.path.join(wiki_root, "AGENTS.md")
        try:
            agents_mtime = os.path.getmtime(agents_path)
            last_discovered = _datetime.fromisoformat(discovered_at)
            if agents_mtime < last_discovered.timestamp():
                print("Config is fresh (discovered {}), skipping.".format(discovered_at))
                # Always refresh raw_paths from actual directory structure
                # even when skipping full discovery — new dirs may have been added.
                raw_source_dirs = _discover_raw_source_dirs(wiki_root)
                if "raw_source_dirs" in config:
                    config["raw_source_dirs"] = raw_source_dirs
                # Refresh vault-level raw_paths from project config (absolute paths).
                pc = load_project_config(wiki_root)
                if pc and "vaults" in config:
                    for vname, vdata in config["vaults"].items():
                        if pc.get("vaults", {}).get(vname, {}).get("wiki_root"):
                            # Absolute wiki_root + raw_paths from config
                            vdata["path"] = pc["vaults"][vname]["wiki_root"]
                            vdata["raw_paths"] = pc["vaults"][vname].get("raw_paths", [])
                        elif "wiki_path" in pc.get("vaults", {}).get(vname, {}):
                            # Legacy: derive from per-vault wiki_path
                            vp = pc["vaults"][vname].get("wiki_path", "")
                            vr = Path(wiki_root) / vp
                            if vr.is_dir():
                                vdata["raw_paths"] = _discover_raw_source_dirs(str(vr))
                config["discovered_at"] = _datetime.now().isoformat()
                config["stale"] = False
                save_cache(cache, cache_path)
                return dict(config)
        except OSError:
            pass  # AGENTS.md missing — force re-discovery

    print("Discovering wiki configuration...")

    # 1. Wiki name from AGENTS.md title
    wiki_name = _extract_wiki_name(wiki_root)

    # 2. Tag routing from AGENTS.md Directory Structure table + actual dirs
    tag_routing, allowed_compiled = _discover_tag_routing(wiki_root)

    # 2b. Parse rules from AGENTS.md (structured checklist section)
    vault_rules = parse_rules(wiki_root)

    # 3. Raw source directories (any subdirectory under Raw/ with .md files)
    raw_source_dirs = _discover_raw_source_dirs(wiki_root)

    # 4. Source tags from AGENTS.md Allowed Tags
    allowed_source = _discover_source_tags(wiki_root)

    # 5. Required fields (defaults — parsed from frontmatter-schema.md in future)
    compiled_required = ["tags", "topics", "sources", "created", "updated"]
    source_required = ["Title", "Reference", "ContentType", "Created"]

    # 5. Paths from directory scan
    templates_dir = "_templates" if (Path(wiki_root) / "_templates").is_dir() else None
    wiki_dir = "Wiki" if (Path(wiki_root) / "Wiki").is_dir() else None
    schema_dir = "Schema" if (Path(wiki_root) / "Schema").is_dir() else None

    # 6. Vault permissions — from project config (.llm-wiki-config/config.json)
    # Project config is the source of truth for which vaults exist and their permissions.
    project_config = load_project_config(wiki_root)

    if project_config:
        # Use vault declarations from project config
        discovered_vaults = {}
        for vname, vinfo in project_config["vaults"].items():
            # Resolve wiki_root for this vault — absolute path from config is source of truth.
            # Falls back to legacy discovery if wiki_root not in config (backward compat).
            vault_root = vinfo.get("wiki_root", "")
            if not vault_root:
                # Legacy: derive from top-level wiki_path
                if "wiki_path" in vinfo and vinfo["wiki_path"]:
                    vault_root = vinfo["wiki_path"]
                else:
                    top_wiki_path = project_config.get("wiki_path", "")
                    if top_wiki_path and os.path.basename(top_wiki_path) == ".llm-wiki":
                        vault_root = os.path.join(top_wiki_path, vname)

            # raw_paths from config (absolute) — primary source.
            # Falls back to disk discovery if not in config or empty (backward compat).
            cfg_raw = vinfo.get("raw_paths", [])
            if not isinstance(cfg_raw, list) or all(not p for p in cfg_raw):
                # No absolute raw_paths in config — discover from disk
                if vault_root == wiki_root or not vault_root:
                    cfg_raw = raw_source_dirs
                elif os.path.isdir(vault_root):
                    vault_raw = Path(vault_root) / "Raw"
                    if vault_raw.is_dir():
                        cfg_raw = _discover_raw_source_dirs(vault_root)

            discovered_vaults[vname] = {
                "path": vault_root,
                "permissions": vinfo.get("permissions", ["read"]),
                "has_raw": bool(cfg_raw),
                "raw_paths": cfg_raw,
            }

    # Add rules_path to each vault (from project config or default AGENTS.md)
    if project_config and "vaults" in project_config:
        for vname, vdata in discovered_vaults.items():
            vr = project_config["vaults"].get(vname, {})
            rp_rel = vr.get("rules_path", {}).get("relative") if isinstance(vr.get("rules_path"), dict) else None
            rp_abs = vr.get("rules_path", {}).get("absolute") if isinstance(vr.get("rules_path"), dict) else None
            if rp_abs:
                vdata["rules_path"] = {"relative": rp_rel or "AGENTS.md", "absolute": rp_abs}
            elif vdata["path"]:
                # Default: AGENTS.md in vault's wiki root
                rp = "AGENTS.md"
                vdata["rules_path"] = {"relative": rp, "absolute": os.path.join(vdata["path"], rp)}
    else:
        # No project config — vaults are not yet declared.
        # Skills should trigger setup flow instead of proceeding.
        discovered_vaults = {}

    # Merge project config defaults into cache (non-null values only).
    # This ensures resolve_model() finds user-configured VL/text models
    # even when cache defaults are null (cache cleared, first run after setup).
    if project_config and "defaults" in project_config:
        proj_defaults = project_config["defaults"]
        cache_defaults = cache.setdefault("defaults", {})
        for field in ("vl_provider", "vl_model_id", "vl_base_url",
                      "text_provider", "text_model_id"):
            val = proj_defaults.get(field)
            if val is not None:
                cache_defaults[field] = val
        # Also merge ingest_vault → default_vault for vault selection
        iv = proj_defaults.get("ingest_vault")
        if iv and not cache_defaults.get("default_vault"):
            cache_defaults["default_vault"] = iv

    # 7. Build config dict
    new_config = {
        "wiki_name": wiki_name,
        "tag_routing": tag_routing,
        "allowed_compiled_tags": allowed_compiled,
        "raw_source_dirs": raw_source_dirs,
        "allowed_source_tags": _discover_source_tags(wiki_root),
        "compiled_required_fields": compiled_required,
        "source_required_fields": source_required,
        "rules": vault_rules,  # parsed from AGENTS.md checklist section
        "paths": {
            "templates_dir": templates_dir,
            "wiki_dir": wiki_dir,
            "schema_dir": schema_dir,
        },
        "vaults": discovered_vaults,
        "discovered_at": _datetime.now().isoformat(),
        "stale": False,
    }

    # Update cache (merge, don't replace — preserves defaults/vl_discovery etc.)
    for key, val in new_config.items():
        config[key] = val

    save_cache(cache, cache_path)
    print("Config discovered: {}, tags={}".format(wiki_name, list(tag_routing.keys())))
    return dict(new_config)


def get_config(wiki_root=None):
    """Read the current config section from cache.

    Convenience function for skills to read discovered config without importing json.

    Args:
        wiki_root: Path to the wiki root. Auto-detected if None.

    Returns:
        dict with config section, or empty dict if not yet discovered.
    """
    cache_path = get_cache_path(wiki_root)
    if not cache_path.exists():
        return {}

    try:
        with open(cache_path) as f:
            cache = json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}

    return cache.get("config", {})


# ---------------------------------------------------------------------------
# Template Caching (in-memory, per-vault, session-scoped)
# ---------------------------------------------------------------------------

# Module-level cache dict — safe for CLI usage (each invocation is a new process).
# For imported usage, cache is per-invocation since it's defined at module level.
def get_cached_template(vault_root, tag):
    """Get template for a note tag. Caches in memory per-vault, session-scoped.

    Templates are small (1-5KB each). Caching reduces disk I/O from 10-50ms
    to ~1μs per read. Zero impact on context window — templates enter context
    either way when notes are created.

    Note: This uses a module-level dict. Safe for CLI usage (new process per run).
    For imported usage in long-running processes, the cache persists across calls.

    Args:
        vault_root: Path to the vault's wiki root directory
        tag: Note type (e.g., 'concept', 'entity', 'topic')

    Returns:
        Template content as string, or None if template not found.
    """
    # Use a local dict per call for safety in imported contexts
    cache_key = f"{vault_root}:{tag}"
    if not hasattr(get_cached_template, "_cache"):
        get_cached_template._cache = {}

    if cache_key in get_cached_template._cache:
        return get_cached_template._cache[cache_key]

    templates_dir = "_templates"
    template_path = os.path.join(vault_root, templates_dir, f"{tag}-note.md")

    if os.path.isfile(template_path):
        with open(template_path, "r", encoding="utf-8") as f:
            content = f.read()
        get_cached_template._cache[cache_key] = content
        return content
    else:
        get_cached_template._cache[cache_key] = None
        return None

def refresh_config(wiki_root=None):
    """Mark config as stale so next discover will re-run."""
    cache_path = get_cache_path(wiki_root)
    if not cache_path.exists():
        return

    cache = load_cache(cache_path)
    config = cache.setdefault("config", {})
    config["stale"] = True
    save_cache(cache, cache_path)


def reset_vault_state():
    """Reset all cached state between vault operations.

    Called by the orchestrator after completing Steps 0-9 for a vault and before
    starting the next. Clears:
    - Template cache (get_cached_template._cache)
    - Config discovery cache (marks config as stale in Schema/.llm-wiki-cache.json)
    - Any other module-level state that could leak between vaults

    This prevents variable leakage even if agents skip instructions.
    Safe to call multiple times; idempotent.

    Note: This is a script-level enforcement of vault isolation. The shared-infra.md
    for each skill instructs agents to call this function between vault operations.
    """
    # Clear template cache
    if hasattr(get_cached_template, "_cache"):
        get_cached_template._cache.clear()

    # Mark config as stale in shared cache (forces re-discovery on next access)
    try:
        cache_path = get_cache_path()
        if cache_path.exists():
            cache = load_cache(cache_path)
            config = cache.setdefault("config", {})
            config["stale"] = True
            save_cache(cache, cache_path)
    except Exception:
        # If we can't access the cache file (e.g., wrong working directory),
        # that's OK — the template cache was already cleared above.
        pass

    # Clear VL discovery cache (forces re-discovery for next vault's context)
    if hasattr(discover_vl_models, "_cache"):
        discover_vl_models._cache.clear()


def check_vl_model_health(cache_path=None):
    """Check if the VL model is available and responsive.

    Pre-parallel warm check for local models: verify the VL model is still loaded
    before spawning VL subagents. Cloud models skip this check (no "loaded/unloaded"
    state).

    Args:
        cache_path: Optional explicit path to the cache file.

    Returns:
        dict with health status:
            {"healthy": bool, "provider": str|None, "model_id": str|None,
             "error": str|null}
    """
    result = {"healthy": False, "provider": None, "model_id": None, "error": None}

    try:
        if cache_path is None:
            cache_path = get_cache_path()

        if not cache_path.exists():
            result["error"] = "Cache file does not exist"
            return result

        cache = load_cache(cache_path)
        discovery = cache.get("vl_discovery", {})

        provider = discovery.get("provider")
        model_id = discovery.get("model_id")

        if not provider or not model_id:
            result["error"] = "VL model not configured in discovery cache"
            return result

        # Check if the provider is a local model (has base_url)
        base_url = discovery.get("base_url")

        if provider == "omlx" and base_url:
            # For local models, do a lightweight health check
            import urllib.request
            try:
                url = f"{base_url}/health"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req, timeout=5) as resp:
                    if resp.status == 200:
                        result["healthy"] = True
                        result["provider"] = provider
                        result["model_id"] = model_id
                    else:
                        result["error"] = f"Health check returned status {resp.status}"
            except Exception as e:
                # Model may be unloaded after inactivity — this is expected
                result["error"] = f"Health check failed (model may be unloaded): {e}"
                result["healthy"] = False
        else:
            # Cloud models: assume healthy if configured (no "loaded/unloaded" state)
            result["healthy"] = True
            result["provider"] = provider
            result["model_id"] = model_id

    except Exception as e:
        result["error"] = f"Health check error: {e}"

    return result


def _detect_wiki_root():
    """Detect wiki root from current working directory.

    Same logic as get_cache_path but returns the parent (wiki root) not cache path.
    """
    cwd = Path.cwd()

    # If we're in a wiki root (has Schema/ and Wiki/), use it
    if (cwd / "Schema").exists() and (cwd / "Wiki").exists():
        return cwd

    # Otherwise, walk up to find a directory with Schema/ and Wiki/
    for parent in list(cwd.parents)[:5]:
        if (parent / "Schema").exists() and (parent / "Wiki").exists():
            return parent

    # Also check immediate children (e.g., wiki root is <parent>/Core/)
    try:
        for child in cwd.iterdir():
            if child.is_dir() and (child / "Schema").exists() and (child / "Wiki").exists():
                return child
    except PermissionError:
        pass

    print("ERROR: Could not detect wiki root. Run from a wiki directory.", file=sys.stderr)
    sys.exit(1)


def _extract_wiki_name(wiki_root):
    """Extract wiki name from AGENTS.md title line."""
    agents_path = os.path.join(wiki_root, "AGENTS.md")
    try:
        with open(agents_path, encoding="utf-8") as f:
            first_line = f.readline().strip()
        # First line is usually "# Agent Rules — LLM Wiki" or similar
        if first_line.startswith("# "):
            name = first_line[2:].strip()
            # Clean up common prefixes: "Agent Rules — LLM Wiki" → "LLM Wiki"
            for prefix in ["Agent Rules", "LLM Wiki"]:
                if name.startswith(prefix):
                    # Strip prefix + optional separator (em-dash, colon, hyphen) + spaces
                    sep = r"[\s]*[-:—]+[\s]*"
                    name = _re.sub(r"^" + _re.escape(prefix) + sep, "", name).strip()
            return name if name else os.path.basename(wiki_root)
    except OSError:
        pass

    # Fallback: use directory name
    return os.path.basename(wiki_root)


def _discover_tag_routing(wiki_root):
    """Discover tag → folder mapping from AGENTS.md + actual directory structure.

    Resolution order:
      1. Read `tag_routing` from AGENTS.md checklist (per-vault custom mapping)
      2. Parse Directory Structure table from AGENTS.md using standard map
      3. Scan actual Wiki/ subdirectories as fallback

    Returns (tag_routing_dict, allowed_compiled_tags_list).
    """
    agents_path = os.path.join(wiki_root, "AGENTS.md")
    tag_routing = {}
    allowed_compiled = set()

    # Standard folder → tag mapping (used by steps 2-3)
    _STANDARD_TAG_MAP = {
        "Topics": "topic",
        "Concepts": "concept",
        "Entities": "entity",
        "Projects": "project",
    }

    # Step 1: Try to read tag_routing from AGENTS.md checklist YAML block
    try:
        with open(agents_path, encoding="utf-8") as f:
            agents_text = f.read()

        # Find the YAML checklist block between ---checklist--- markers
        list_start = agents_text.find("---checklist---")
        if list_start >= 0:
            after_marker = agents_text[list_start + len("---checklist---"):]
            start_idx = after_marker.find("\n") + 1 if "\n" in after_marker else 0
            close_idx = after_marker.find("\n---", start_idx)
            if close_idx > 0:
                yaml_block = after_marker[start_idx:close_idx].strip()
                if yaml_block:
                    # Try YAML parsing first
                    try:
                        import yaml  # type: ignore

                        parsed = yaml.safe_load(yaml_block)
                        if isinstance(parsed, dict) and "tag_routing" in parsed:
                            tr = parsed["tag_routing"]
                            if isinstance(tr, dict):
                                for folder_name, tag in tr.items():
                                    tag = str(tag).strip().lstrip("-").strip()
                                    folder_path = "Wiki/{}".format(folder_name)
                                    tag_routing[tag] = folder_path
                                    allowed_compiled.add(tag)
                    except Exception:
                        pass  # Fall through to step 2
    except OSError:
        pass

    # Step 2: Parse Directory Structure table from AGENTS.md (standard map)
    if not tag_routing:
        try:
            with open(agents_path, encoding="utf-8") as f:
                agents_text = f.read()

            dir_match = _re.search(
                r"^## Directory Structure\s*\n(.*?)(?=^## |\Z)",
                agents_text, flags=_re.MULTILINE | _re.DOTALL
            )
            if dir_match:
                table_text = dir_match.group(1)
                for match in _re.finditer(r"\|\s*`(Wiki/\w+)`", table_text):
                    folder_name = match.group(1).split("/")[-1]
                    if folder_name in _STANDARD_TAG_MAP:
                        tag = _STANDARD_TAG_MAP[folder_name]
                        tag_routing[tag] = match.group(1)
                        allowed_compiled.add(tag)
        except OSError:
            pass

    # Step 3: Fallback — scan actual Wiki/ subdirectories (standard map)
    if not tag_routing:
        wiki_dir = Path(wiki_root) / "Wiki"
        if wiki_dir.is_dir():
            for entry in sorted(wiki_dir.iterdir()):
                if entry.is_dir():
                    folder_name = entry.name
                    if folder_name in _STANDARD_TAG_MAP:
                        tag = _STANDARD_TAG_MAP[folder_name]
                        tag_routing[tag] = "Wiki/{}".format(entry.name)
                        allowed_compiled.add(tag)

    return tag_routing, sorted(allowed_compiled)


def _discover_raw_source_dirs(wiki_root):
    """Discover subdirectories under Raw/ that contain source .md files.

    Scans all immediate children of Raw/ for directories containing markdown files
    with frontmatter (title, source fields). This captures any "to be ingested"
    directory regardless of name (Sources, Source, Ingest, etc.).

    Returns:
        list of relative paths like ["Raw/Sources", "Raw/Source", "Raw/Ingest"]
    """
    raw_dir = Path(wiki_root) / "Raw"
    if not raw_dir.is_dir():
        return []

    source_dirs = []
    for entry in sorted(raw_dir.iterdir()):
        if not entry.is_dir():
            continue
        # Check for .md files with frontmatter in this directory (non-recursive)
        md_files = list(entry.glob("*.md"))
        has_source_md = False
        for md in md_files:
            try:
                with open(md, encoding="utf-8") as f:
                    first_line = f.readline().strip()
                if first_line == "---":
                    has_source_md = True
                    break
            except (OSError, UnicodeDecodeError):
                pass
        if has_source_md:
            source_dirs.append("Raw/{}".format(entry.name))

    return source_dirs


def parse_rules(wiki_root=None, rules_path_rel="AGENTS.md"):
    """Parse structured checklist from AGENTS.md (or custom rules file).

    Looks for a YAML block between ---checklist--- markers on their own lines.
    Falls back to defaults if no checklist section is found or parsing fails.

    Args:
        wiki_root: Path to the vault's wiki root directory.
        rules_path_rel: Relative path from wiki_root to the rules file (default: AGENTS.md).

    Returns:
        dict with parsed rule constraints.
    """
    defaults = {
        "required_sections": ["## Related", "## Sources"],
        "allowed_tags": [],  # empty = no restriction
        "topics_required_for": ["concept", "entity"],
        "source_count_required": True,
        "max_topics": 5,  # max topics per compiled note (optional — absent = no limit)
        "tag_routing": {},  # vault-specific folder → tag mapping (optional)
    }

    if wiki_root is None:
        return defaults

    rules_file = Path(wiki_root) / rules_path_rel
    if not rules_file.is_file():
        return defaults

    try:
        content = rules_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return defaults

    # Split into lines and find checklist markers on their own line
    lines = content.split("\n")
    start_line_idx = None
    end_line_idx = None

    for i, line in enumerate(lines):
        stripped = line.strip()
        if start_line_idx is None and stripped == "---checklist---":
            start_line_idx = i
        elif start_line_idx is not None and stripped == "---" and i > start_line_idx + 1:
            # Found closing marker on its own line, at least one content line after start
            end_line_idx = i
            break

    if start_line_idx is None or end_line_idx is None:
        return defaults

    # Extract YAML block (lines between the two markers)
    yaml_lines = lines[start_line_idx + 1:end_line_idx]
    yaml_block = "\n".join(yaml_lines).strip()

    if not yaml_block:
        return defaults

    # Try YAML parsing first, then fallback to basic key-value parser
    try:
        import yaml  # type: ignore
        parsed = yaml.safe_load(yaml_block)
        if isinstance(parsed, dict):
            for key in defaults:
                if key not in parsed:
                    parsed[key] = defaults[key]
            return parsed
    except Exception:
        pass  # Fall back to basic parser below

    return _parse_rules_basic(yaml_block, defaults)


def _parse_rules_basic(yaml_block, defaults):
    """Fallback parser for rules when yaml module is unavailable."""
    result = dict(defaults)

    # Group lines into key-value pairs, handling YAML-style lists
    current_key = None
    list_values = {}
    lines = yaml_block.split("\n")

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("- "):
            # List item — append to current key's list
            val = stripped[2:].strip().strip('"').strip("'")
            if current_key and current_key in defaults:
                list_values.setdefault(current_key, []).append(val)
        elif ":" in stripped:
            # Flush any pending list values
            if current_key and current_key in defaults and current_key in list_values:
                result[current_key] = list_values.pop(current_key)

            key, _, val = stripped.partition(":")
            key = key.strip()
            if not val:
                # Start of a list: next lines with "- " belong to this key
                current_key = key if key in defaults else None
            elif ":" not in val and "[" not in val:
                # Could be start of inline list — check next line
                current_key = key if key in defaults else None
            elif ":" in val:
                # Inline dict value, skip
                current_key = None
            else:
                val = val.strip().strip('"').strip("'")
                current_key = None
                if key not in defaults:
                    continue
                if key == "source_count_required":
                    result[key] = val.lower() in ("true", "1", "yes")
                elif key == "max_topics":
                    try:
                        result[key] = int(val)
                    except ValueError:
                        pass
                elif key == "allowed_tags":
                    if val.startswith("[") and "]" in val:
                        tags_str = val[1:val.index("]")]
                        result[key] = [t.strip().strip('"').strip("'") for t in tags_str.split(",") if t.strip()]
                elif key == "tag_routing":
                    # Parse inline list: [Topics/topic, Concepts/concept] or [folder/tag, ...]
                    if val.startswith("[") and "]" in val:
                        entries_str = val[1:val.index("]")]
                        tag_routing_dict = {}
                        for entry in entries_str.split(","):
                            entry = entry.strip().strip('"').strip("'")
                            if "/" in entry:
                                folder, tag = entry.split("/", 1)
                                tag_routing_dict[folder.strip()] = tag.strip()
                        if tag_routing_dict:
                            result[key] = tag_routing_dict
    
    # Flush last pending list
    if current_key and current_key in defaults and current_key in list_values:
        result[current_key] = list_values.pop(current_key)

    return result


def _discover_source_tags(wiki_root):
    """Discover allowed tags for Raw source frontmatter.

    Reads `source_tag` from AGENTS.md's checklist (per-vault configurable).
    Falls back to ["source"] if not defined.

    Per original design, source notes use the tag [source] to identify
    themselves as raw sources. This is NOT a routing tag — it's an identifier.
    Type metadata (youtube, article, clipping) goes in ContentType field instead.

    Args:
        wiki_root: Path to the vault's wiki root directory (for AGENTS.md lookup).

    Returns:
        list with the allowed source tag value (typically ["source"]).
    """
    defaults = {"source_tag": ["source"]}

    if wiki_root is None:
        return defaults["source_tag"]

    rules_file = Path(wiki_root) / "AGENTS.md"
    if not rules_file.is_file():
        return defaults["source_tag"]

    try:
        content = rules_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return defaults["source_tag"]

    # Find the YAML checklist block between ---checklist--- markers
    list_start = content.find("---checklist---")
    if list_start < 0:
        return defaults["source_tag"]

    after_marker = content[list_start + len("---checklist---"):]
    start_idx = after_marker.find("\n") + 1 if "\n" in after_marker else 0
    close_idx = after_marker.find("\n---", start_idx)
    if close_idx <= 0:
        return defaults["source_tag"]

    yaml_block = after_marker[start_idx:close_idx].strip()
    if not yaml_block:
        return defaults["source_tag"]

    # Try YAML parsing first
    try:
        import yaml  # type: ignore
        parsed = yaml.safe_load(yaml_block)
        if isinstance(parsed, dict) and "source_tag" in parsed:
            st = parsed["source_tag"]
            if isinstance(st, list):
                return [str(t).strip().lstrip("-").strip() for t in st]
            return [str(st).strip().lstrip("-").strip()]
    except Exception:
        pass

    # Fallback: basic parser for source_tag (inline list)
    lines = yaml_block.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("source_tag:") and "[" in stripped:
            val = stripped.split(":", 1)[1].strip()
            if "]" in val:
                tags_str = val[1:val.index("]")]
                return [t.strip().strip('"').strip("'") for t in tags_str.split(",") if t.strip()]

    return defaults["source_tag"]


def _discover_content_types(wiki_root):
    """Discover allowed content types for Raw source frontmatter.

    Reads `allowed_content_types` from AGENTS.md's checklist (per-vault configurable).
    Returns all lowercase for case-insensitive comparison.

    Args:
        wiki_root: Path to the vault's wiki root directory (for AGENTS.md lookup).

    Returns:
        list of allowed content type strings, lowercased (e.g., ["video", "article"]).
    """
    defaults = []  # empty = no restriction (any ContentType accepted)

    if wiki_root is None:
        return defaults

    rules_file = Path(wiki_root) / "AGENTS.md"
    if not rules_file.is_file():
        return defaults

    try:
        content = rules_file.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return defaults

    # Find the YAML checklist block between ---checklist--- markers
    list_start = content.find("---checklist---")
    if list_start < 0:
        return defaults

    after_marker = content[list_start + len("---checklist---"):
    ]
    start_idx = after_marker.find("\n") + 1 if "\n" in after_marker else 0
    close_idx = after_marker.find("\n---", start_idx)
    if close_idx <= 0:
        return defaults

    yaml_block = after_marker[start_idx:close_idx].strip()
    if not yaml_block:
        return defaults

    # Try YAML parsing first (handles both source_tag and allowed_content_types)
    try:
        import yaml  # type: ignore
        parsed = yaml.safe_load(yaml_block)
        if isinstance(parsed, dict):
            act = parsed.get("allowed_content_types")
            if isinstance(act, list):
                return [str(t).strip().lower() for t in act]
    except Exception:
        pass

    # Fallback: basic parser for allowed_content_types (inline list)
    lines = yaml_block.split("\n")
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith("allowed_content_types:") and "[" in stripped:
            val = stripped.split(":", 1)[1].strip()
            if "]" in val:
                types_str = val[1:val.index("]")]
                return [t.strip().strip('"').strip("'").lower() for t in types_str.split(",") if t.strip()]

    return defaults


def get_wiki_root(wiki_name=None):
    """Get the wiki root path for a given vault name.

    Resolution order:
      1. Auto-detect from cwd (this wiki)
      2. Resolve via project config (.llm-wiki-config/config.json) if wiki_name provided
      3. Fall back to cwd detection

    Args:
        wiki_name: Vault name (e.g., "Core"). If None, auto-detects from cwd.

    Returns:
        Path object to the wiki root directory, or None if not found.
    """
    detected = _detect_wiki_root()

    # If no specific vault requested, return auto-detected
    if not wiki_name:
        return detected

    # Try project config first (authoritative source for vault → wiki root mapping)
    proj_config = load_project_config()
    if proj_config and wiki_name in proj_config.get("vaults", {}):
        vinfo = proj_config["vaults"][wiki_name]

        # Priority 1: per-vault wiki_path (explicit override)
        if "wiki_path" in vinfo and vinfo["wiki_path"]:
            candidate = Path(vinfo["wiki_path"])
            if (candidate / "Wiki").exists() and (candidate / "Schema").exists():
                return candidate
            if candidate.exists() and (candidate / "Wiki").exists():
                return candidate
            # Also check if it's the parent .llm-wiki/ directory (derive vault root)
            if candidate.is_dir():
                derived = candidate / wiki_name
                if (derived / "Wiki").exists() and (derived / "Schema").exists():
                    return derived
                # Also try nested: .llm-wiki/<wiki_name>
                if candidate.name == ".llm-wiki" or (candidate / ".llm-wiki").is_dir():
                    nested = candidate / wiki_name
                    if (nested / "Wiki").exists():
                        return nested
            # Path exists but Wiki/Schema not found — still use it (might be a different structure)
            if candidate.exists():
                return candidate

        # Priority 2: derive from top-level wiki_path
        top_wiki = proj_config.get("wiki_path", "")
        if top_wiki:
            # If it points to a parent .llm-wiki/, derive vault root
            top_path = Path(top_wiki)
            if os.path.basename(top_wiki) == ".llm-wiki":
                candidate = top_path / wiki_name
                if (candidate / "Wiki").exists() and (candidate / "Schema").exists():
                    return candidate
                if candidate.exists() and (candidate / "Wiki").exists():
                    return candidate
            # If it points directly to a wiki root, try sibling derivation
            elif top_path.exists() and (top_path / "Wiki").exists():
                parent = top_path.parent
                candidate = parent / wiki_name
                if (candidate / "Wiki").exists() and (candidate / "Schema").exists():
                    return candidate

    # Last resort: same wiki as cwd (might be the requested vault)
    return detected



def resolve_model(task, cache_path=None):
    """Resolve which model to use for a given task.

    Reads from project config (.llm-wiki-config/config.json) — the source of truth.
    Falls back to cache defaults only if project config is unavailable.

    Args:
        task: Task name, e.g., "image_ingest", "note_generation".
        cache_path: Optional explicit path to the shared cache file (fallback).

    Returns:
        dict with keys: provider, model_id, base_url (VL tasks) or
        provider, model_id (text tasks). Values are None if not configured.
    """
    # Primary: read from project config (source of truth)
    proj_config = load_project_config()

    if task.startswith(("image_", "video_")):
        # VL tasks — return all three fields from project config defaults
        if proj_config and "defaults" in proj_config:
            d = proj_config["defaults"]
        else:
            # Fallback: read from cache defaults
            if cache_path is None:
                cache_path = get_cache_path()
            d = load_cache(cache_path).get("defaults", {})
        return {
            "provider": d.get("vl_provider"),
            "model_id": d.get("vl_model_id"),
            "base_url": d.get("vl_base_url"),
        }
    else:
        # Text tasks — return provider and model_id from project config defaults
        if proj_config and "defaults" in proj_config:
            d = proj_config["defaults"]
        else:
            if cache_path is None:
                cache_path = get_cache_path()
            d = load_cache(cache_path).get("defaults", {})
        return {
            "provider": d.get("text_provider"),
            "model_id": d.get("text_model_id"),
        }


def set_default(field, value, cache_path=None):
    """Set a shared default in the cache and project config.

    Writes to both cache (immediate runtime) and project config file
    (persists across sessions). Only VL/text fields are synced to
    project config; other defaults stay in cache only.

    Args:
        field: Field name, e.g., "vl_provider", "text_model_id".
        value: Value to set.
        cache_path: Optional explicit path to the shared cache file.

    Returns:
        Path where cache was saved.
    """
    if cache_path is None:
        cache_path = get_cache_path()

    cache = load_cache(cache_path)
    cache.setdefault("defaults", {})[field] = value
    save_cache(cache, cache_path)

    # Also persist to project config for VL/text fields.
    _persist_default_to_project_config(field, value)

    return cache_path


def _persist_default_to_project_config(field, value):
    """Write a VL/text default field to project config if it exists."""
    persistable_fields = ("vl_provider", "vl_model_id","vl_base_url",
                          "text_provider", "text_model_id")

    if field not in persistable_fields:
        return

    config_dir = find_project_config()
    if not config_dir:
        return  # No project config — cache is sufficient

    config_file = config_dir / _PROJECT_CONFIG_FILE
    if not config_file.exists():
        return

    try:
        with open(config_file) as f:
            config = json.load(f)
    except (json.JSONDecodeError, IOError):
        return

    defaults = config.setdefault("defaults", {})
    # Map field names: cache uses "text_model_id" but project config also has
    # ingest_vault → default_vault mapping (handled separately)
    defaults[field] = value

    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)


def set_task_override(task, field, value, cache_path=None):
    """Set a per-task override in the cache.

    Args:
        task: Task name, e.g., "image_ingest", "video_analysis".
        field: Field name, e.g., "vl_model_id", "text_model_id".
        value: Value to set.
        cache_path: Optional explicit path to the shared cache file.

    Returns:
        Path where cache was saved.
    """
    if cache_path is None:
        cache_path = get_cache_path()

    cache = load_cache(cache_path)
    overrides = cache.setdefault("task_overrides", {}).setdefault(task, {})

    # Map field names to override keys
    if "vl_" in field:
        overrides[field] = value
    elif "text_" in field:
        overrides[field] = value

    return save_cache(cache, cache_path)


# ─── CLI Entry Points ─────────────────────────────────────────────

def main():
    """CLI interface for shared wiki utilities.

    Usage:
        python3 scripts/wiki_shared.py find-project-config     # Print config dir path or "not found"
        python3 scripts/wiki_shared.py discover [--force]       # Run VL discovery
        python3 scripts/wiki_shared.py vaults                  # List declared vaults + permissions
        python3 scripts/wiki_shared.py models <task>           # Show resolved model for task
        python3 scripts/wiki_shared.py set-default <field> <value>  # Set a default
        python3 scripts/wiki_shared.py set-override <task> <field> <value>  # Set task override
        python3 scripts/wiki_shared.py status                  # Show full cache state
        python3 scripts/wiki_shared.py config [--force]        # Discover wiki structure + project config
    """
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "find-project-config":
        config_dir = find_project_config()
        if config_dir:
            print(config_dir)
        else:
            print("not found")

    elif cmd == "discover":
        force = "--force" in sys.argv[2:]
        result = discover_vl_models(force=force)
        print(json.dumps(result, indent=2))

    elif cmd == "vaults":
        # Read vault declarations from project config (authoritative source)
        proj_config = load_project_config()
        if not proj_config:
            print("No project config found (.llm-wiki-config/config.json).")
            sys.exit(1)
        for vname, vinfo in proj_config["vaults"].items():
            perms = ",".join(vinfo.get("permissions", []))
            print(f"{vname} [{perms}]")

    elif cmd == "models":
        if len(sys.argv) < 3:
            print("Usage: wiki_shared.py models <task>", file=sys.stderr)
            sys.exit(1)

        task = sys.argv[2]
        model = resolve_model(task)
        print(json.dumps(model, indent=2))

    elif cmd == "set-default":
        if len(sys.argv) < 4:
            print("Usage: wiki_shared.py set-default <field> <value>", file=sys.stderr)
            sys.exit(1)

        field, value = sys.argv[2], sys.argv[3]
        set_default(field, value)
        print(f"Set defaults.{field} = {value}")

    elif cmd == "set-override":
        if len(sys.argv) < 5:
            print("Usage: wiki_shared.py set-override <task> <field> <value>", file=sys.stderr)
            sys.exit(1)

        task, field, value = sys.argv[2], sys.argv[3], sys.argv[4]
        set_task_override(task, field, value)
        print(f"Set task_overrides.{task}.{field} = {value}")

    elif cmd == "status":
        cache_path = get_cache_path()
        if not cache_path.exists():
            print("No shared cache found.")
            sys.exit(0)

        with open(cache_path) as f:
            cache = json.load(f)
        print(json.dumps(cache, indent=2))

    elif cmd == "config":
        force = "--force" in sys.argv[2:]

        # Check project config first (authoritative)
        proj_config = load_project_config()
        if not proj_config:
            print("No project config found (.llm-wiki-config/config.json).")
            print("Run the setup skill to create one.")
        else:
            config_dir = find_project_config()
            print(f"Project config: {config_dir / _PROJECT_CONFIG_FILE}")
            for vname, vinfo in proj_config["vaults"].items():
                perms = ",".join(vinfo.get("permissions", []))
                print(f"  {vname} [{perms}]")

        # Run wiki discovery to populate cache (vaults, raw_paths, tag_routing, etc.)
        discovered = discover_config(force=force)
        if discovered and "vaults" in discovered:
            for vname, vdata in discovered["vaults"].items():
                raw = ",".join(vdata.get("raw_paths", [])) or "(none)"
                print(f"  {vname} raw_paths: [{raw}]")

    elif cmd == "refresh-config":
        refresh_config()
        print("Config marked stale. Re-discovering...")
        discovered = discover_config(force=True)
        if discovered and "vaults" in discovered:
            for vname, vdata in discovered["vaults"].items():
                raw = ",".join(vdata.get("raw_paths", [])) or "(none)"
                print(f"  {vname} raw_paths: [{raw}]")

    elif cmd == "cache-clear":
        # Clear the shared config cache (Schema/.llm-wiki-cache.json)
        # The template cache is in-memory and per-invocation (safe for CLI).
        cache_path = get_cache_path()
        if not cache_path.exists():
            print("No shared config cache found.")
        else:
            import shutil
            # Backup cache before clearing
            backup = str(cache_path) + ".bak"
            shutil.copy2(str(cache_path), backup)
            cache_path.unlink()
            print(f"Config cache cleared. Backup saved to {backup}")

    elif cmd == "template":
        # Get a cached template for the current vault
        if len(sys.argv) < 3:
            print("Usage: wiki_shared.py template <tag>", file=sys.stderr)
            sys.exit(1)
        tag = sys.argv[2]
        wiki_root = _detect_wiki_root()
        if not wiki_root:
            print("ERROR: Cannot detect wiki root.", file=sys.stderr)
            sys.exit(1)
        content = get_cached_template(wiki_root, tag)
        if content is None:
            print(f"Template '{tag}-note.md' not found in {wiki_root}/_templates/")
            sys.exit(1)
        print(content, end="")  # Don't add extra newline

    elif cmd == "reset-vault":
        # Reset all cached state between vault operations
        reset_vault_state()
        print("Vault state reset complete (templates cleared, config marked stale)")

    elif cmd == "vl-health-check":
        # Check if VL model is available and responsive
        result = check_vl_model_health()
        print(json.dumps(result, indent=2))

    else:
        print(f"Unknown command: {cmd}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
