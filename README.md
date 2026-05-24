# LLM Wiki Installer

Portable installer for the [LLM Wiki](https://github.com/.../Pi-Vault) knowledge base system. Creates a structured Obsidian vault optimized for agentic AI workflows.

## Quick Start

### Human (interactive)
Double-click `Install.command` in Finder, or run:
```bash
bash Install.command
```

### Agent (non-interactive)
Set environment variables and run:
```bash
export SETUP_MODE=1 SETUP_VAULT_NAME="MyWiki"
bash run.sh
```

## How It Works

1. Discovers existing Obsidian vaults or creates a new `.llm-wiki/` folder
2. Copies system files (AGENTS.md, Schema/, _templates/, scripts/, .agents/skills/)
3. Registers the vault with Obsidian (writes to `obsidian.json`)
4. Writes vault path to `~/.pi/pi-vault-path` for skill discovery
5. Runs initial validation (build, lint)

After installation, the installer folder is automatically cleaned up from the parent directory.

## Requirements

- macOS (or any OS with Obsidian)
- Python 3.x
- [Obsidian CLI](https://github.com/obsidian-community/obsidian-cli) (`npm install -g obsidian`)
- Obsidian app running (for vault registration)

## What Gets Installed

| Path | Purpose |
|------|---------|
| `AGENTS.md` | Agent instructions, workflow reference |
| `Wiki/` | Compiled knowledge (Concepts, Topics, Entities) |
| `Raw/Sources/` | Raw source material (never modified after ingest) |
| `Schema/` | Rules, schemas, validation definitions |
| `_templates/` | Note templates for new Wiki notes |
| `scripts/wiki_tool.py` | Validation tools (build, lint, search-catalog) |
| `.agents/skills/` | Agent skills (ingest, query, lint, maintain) |

## License

Same as Pi-Vault.
