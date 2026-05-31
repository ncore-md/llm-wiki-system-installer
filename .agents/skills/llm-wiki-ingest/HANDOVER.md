# Handover — VL Model Config from Project Setup

## Goal
Make the VL model definition come from `.llm-wiki-config/config.json` (set by `llm-wiki-setup` wizard), not from pi's global `~/.pi/agent/models.json`. The ingest skill should just read config.

## Current State
- `~/.pi/agent/models.json` defines omlx provider with VL model: `qwen3.6-35b-a3b-mlx-vl-oQ4-FP16`
- `wiki_shared.py/resolve_model("image_ingest")` reads from cache defaults → falls back to `vl_discovery` (from pi models.json)
- `.llm-wiki-config/config.json` has `defaults.vl_model_id: null` but it's never merged into cache
- Setup wizard writes VL to wiki cache via `set-default`, NOT to project config

## What Was Done (in this session)
1. **Simplified ingest skill Step 0** — removed Options A/B/C, single subagent path with `llm-wiki-vl` skill
2. **Updated source validation** for images to reference subagent approach  
3. **Added explicit "No VL model found"** notification (don't skip silently)
4. **wiki_shared.py edits** — 2 of 3 succeeded:
   - ✅ Added `defaults` validation in `load_project_config()` — validates ingest_vault, vl_provider/model_id/base_url
   - ✅ Added VL merge in `discover_config()` — copies project config defaults into cache
   - ❌ Failed to edit `resolve_model()` — couldn't match exact text (whitespace issue)

## What Still Needs To Be Done
1. **Fix `resolve_model()` in wiki_shared.py** — update the VL resolution to prioritize project config defaults. The edit failed due to exact text matching. Read lines ~926-935 of the file and apply:
   ```python
   # Change from:
   if task.startswith(("image_", "video_")):
       provider = defaults.get("vl_provider") or cache.get("vl_discovery", {}).get("provider")
       model_id = defaults.get("vl_model_id") or cache.get("vl_discovery", {}).get("model_id")
       base_url = defaults.get("vl_base_url") or cache.get("vl_discovery", {}).get("base_url")
       return {"provider": provider, "model_id": model_id}
   
   # To:
   if task.startswith(("image_", "video_")):
       provider = defaults.get("vl_provider") or cache.get("vl_discovery", {}).get("provider")
       model_id = defaults.get("vl_model_id") or cache.get("vl_discovery", {}).get("model_id")
       base_url = defaults.get("vl_base_url") or cache.get("vl_discovery", {}).get("base_url")
       if provider and model_id:
           return {"provider": provider, "model_id": model_id}
       disc = cache.get("vl_discovery", {})
       return {"provider": disc.get("provider") or provider, "model_id": disc.get("model_id") or model_id}
   ```

2. **Update setup wizard** (`/Users/bernardoresende/.agents/skills/llm-wiki-setup/SKILL.md`) — step 5c and step 6:
   - Step 5c should write VL settings to project config (not just wiki cache)
   - Ask user: provider, model_id, base_url for VL model  
   - Step 6 config example should include `vl_provider`, `vl_model_id` in defaults
   - Current step 6 example only shows `vl_model_id: null`, needs actual values

3. **Update config.json** (`/Users/bernardoresende/Core/.llm-wiki-config/config.json`):
   ```json
   {
     "wiki_path": "/Users/bernardoresende/Core/.llm-wiki",
     "vaults": {
       "Core": { "permissions": ["read","write","ingest","maintain"] }
     },
     "defaults": {
       "ingest_vault": "Core",
       "text_model_id": null,
       "vl_provider": "omlx",
       "vl_model_id": "qwen3.6-35b-a3b-mlx-vl-oQ4-FP16",
       "vl_base_url": "http://localhost:8000/v1"
     }
   }
   ```

4. **Verify end-to-end**: Run `wiki_shared.py config --force` then check that `resolve_model("image_ingest")` returns the omlx model from project config, not discovery.

## Key Files
- **wiki_shared.py**: `/Users/bernardoresende/Core/.llm-wiki-Core/scripts/wiki_shared.py`
- **Setup skill**: `/Users/bernardoresende/.agents/skills/llm-wiki-setup/SKILL.md`
- **Ingest skill**: `/Users/bernardoresende/.agents/skills/llm-wiki-ingest/SKILL.md`
- **VL skill**: `/Users/bernardoresende/.agents/skills/llm-wiki-vl/SKILL.md`
- **Config**: `/Users/bernardoresende/Core/.llm-wiki-config/config.json`
- **Pi models**: `/Users/bernardoresende/.pi/agent/models.json`

## Flow After Fix
1. User runs setup wizard → writes VL settings to `.llm-wiki-config/config.json`
2. `discover_config()` merges project config defaults into cache
3. Ingest skill calls `resolve_model("image_ingest")` → returns VL model from config
4. Subagent spawned with `model: "omlx/qwen3.6-..."` and skill `llm-wiki-vl`

## Previous Session Notes
- Source format: wikilinks `"[[wikilink]]"` in YAML frontmatter (all templates/docs updated)
- Topic validation: lint enforces ≥1 topic for concept/entity notes, accepts wikilink format
- raw_paths: auto-populated from Raw/ directory structure in discover_config()
