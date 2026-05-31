## Pre-flight Check (Required Before Consolidation)

**Before attempting consolidation, verify config is usable.** If it's missing or empty, offer setup.

1. **Check vaults:** Verify that at least one vault is configured in `.llm-wiki-config/config.json`
2. **Check VL output:** Ensure `$VL_OUTPUT_FILE` exists and contains parsed notes

## Vault Isolation Rule (All Skills)
When the orchestrator processes multiple vaults, `reset_vault_state()` is called between each vault. This clears all cached config-derived state (templates, search index, discovered paths). Always call `reset_vault_state()` after completing Steps 0-9 for a vault and before starting the next.

## Consolidation Positioning
The consolidate skill runs AFTER VL batch completion and BEFORE text source processing (Steps 1-9). This allows the orchestrator to:
1. Evaluate VL outputs and produce a decision document
2. Execute note writes via `obsidian_write`/`obsidian_append` based on consolidation decisions
3. Continue with text source processing (Steps 1-9) knowing the VL-derived state is already resolved
