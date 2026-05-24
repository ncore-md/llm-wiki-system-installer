# Instalador LLM Wiki

Instalador portátil para o sistema de base de conhecimento [LLM Wiki](https://github.com/ncore-md/Pi-Vault). Cria um repositório estruturado no Obsidian otimizado para fluxos de trabalho com IA agente.

## Início Rápido

### Comando único (recomendado)
```bash
gh repo clone ncore-md/llm-wiki-system-installer && cd llm-wiki-system-installer && open Install.command
```

### Humano (interativo)
Clique duas vezes em `Install.command` no Finder, ou execute:
```bash
bash Install.command
```

### Agente (não-interativo)
Defina variáveis de ambiente e execute:
```bash
export SETUP_MODE=1 SETUP_VAULT_NAME="MinhaWiki"
bash run.sh
```

## Como Funciona

1. Descobre repositórios Obsidian existentes ou cria uma nova pasta `.llm-wiki/`
2. Copia arquivos do sistema (AGENTS.md, Schema/, _templates/, scripts/.agents/skills/)
3. Registra o repositório no Obsidian (escreve em `obsidian.json`)
4. Escreve o caminho do repositório em `~/.pi/pi-vault-path` para descoberta de skills
5. Executa validação inicial (build, lint)

Após a instalação, a pasta do instalador é automaticamente removida do diretório pai.

## Requisitos

- macOS (ou qualquer OS com Obsidian)
- Python 3.x
- [Obsidian CLI](https://github.com/obsidian-community/obsidian-cli) (`npm install -g obsidian`)
- Aplicativo Obsidian em execução (para registro do repositório)

## O Que é Instalado

| Caminho | Propósito |
|---------|-----------|
| `AGENTS.md` | Instruções para agentes, referência de workflow |
| `Wiki/` | Conhecimento compilado (Concepts, Topics, Entities) |
| `Raw/Sources/` | Material bruto de fontes (não modificado após ingestão) |
| `Schema/` | Regras, esquemas, definições de validação |
| `_templates/` | Modelos de nota para novas notas Wiki |
| `scripts/wiki_tool.py` | Ferramentas de validação (build, lint, search-catalog) |
| `.agents/skills/` | Skills de agentes (ingest, query, lint, maintain) |

## Licença

[Uso Livre](LICENSE) — sem restrições, use por sua conta e risco.
