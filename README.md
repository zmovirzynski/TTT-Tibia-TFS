# TTT — OTServer Developer Toolkit

> Toolkit para desenvolvimento OTServ: converte, analisa, corrige e documenta scripts Lua e XML entre versões do TFS.

[![Python 3.7+](https://img.shields.io/badge/python-3.7%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-295%20passing-brightgreen.svg)]()

---

## Estado Atual

O TTT é um toolkit funcional com núcleo estável e algumas áreas em amadurecimento. A tabela abaixo reflete o estado real de cada módulo:

### Maturidade por Módulo

| Módulo | Comando | Status | Notas |
|--------|---------|:------:|-------|
| Conversor | `ttt convert` | **Stable** | 217+ mapeamentos, 23 assinaturas, 243 constantes |
| Linter | `ttt lint` | **Stable** | 10 regras, 3 formatos de saída |
| Auto-Fixer | `ttt fix` | **Stable** | 5 regras de correção, dry-run, diff, backup |
| Analyzer | `ttt analyze` | **Stable** | 6 módulos de análise (stats, dead_code, duplicates, storage, items, complexity) |
| Doctor | `ttt doctor` | **Stable** | 6 health checks + validação XML |
| Docs Generator | `ttt docs` | **Stable** | HTML, Markdown, JSON |
| Script Generator | `ttt create` | **Stable** | Templates RevScript e TFS 1.x |
| Formatter | `ttt format` | **Beta** | Indentação, operadores, tabelas Lua |
| Test Framework | `ttt test` | **Beta** | Mocks OTServ + runner unittest. Veja [nota sobre ttt test](#nota-sobre-ttt-test) |
| Conversão AST | `--use-ast` | **Experimental** | Requer `luaparser`. Veja [dependências opcionais](#dependências-opcionais) |
| VS Code Extension | — | **Beta** | Autocomplete, hover, diagnostics, quick fix. Veja [vscode-extension/](vscode-extension/) |
| NPC Conversation Analyzer | — | **Stub** | Estrutura existe, implementação pendente. Não integrado ao CLI |
| Server Migrator | — | **Backlog** | Planejado, não implementado |

**Legenda:** **Stable** = testado e confiável · **Beta** = funcional, pode ter arestas · **Experimental** = requer dependência opcional, pode ter limitações · **Stub** = estrutura criada, sem lógica real

---

## Instalação

### Uso básico (zero dependências)

```bash
git clone https://github.com/zmovirzynski/TTT-Tibia-TFS-Transpiler.git
cd TTT-Tibia-TFS-Transpiler
python run.py --help
```

### Como pacote

```bash
pip install -e .
ttt --help
```

### Para desenvolvimento / contribuição

```bash
git clone https://github.com/zmovirzynski/TTT-Tibia-TFS-Transpiler.git
cd TTT-Tibia-TFS-Transpiler
python -m venv .venv

# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -e .
pip install pytest>=7.0 ruff>=0.4.0

# Rodar a suite de testes
python -m pytest tests/ -v
```

### Dependências opcionais

| Pacote | Para quê | Como instalar |
|--------|----------|---------------|
| `luaparser` | Modo AST (`--use-ast` no analyze, conversão AST) | `pip install luaparser` |
| `pytest` | Rodar a suite de testes do projeto | `pip install pytest` |
| `ruff` | Lint/format do código Python do próprio TTT | `pip install ruff` |

**Sobre o `--use-ast`:** Quando `luaparser` não está instalado, features AST são desabilitadas silenciosamente. Sem a dependência, `--use-ast` no analyze não produz resultados de duplicatas semânticas. O conversor AST (`ast_lua_transformer.py`) faz fallback automático para o motor regex.

**Limitações conhecidas do modo AST:**
- Dependência externa (`luaparser>=3.0`)
- Pode falhar em scripts Lua com sintaxe não-padrão
- Duplicatas semânticas são experimentais — use como indicativo, não como verdade absoluta

---

## Uso Rápido

### Modo Interativo (Wizard)

```bash
python run.py
```

### Converter Scripts

```bash
# Conversão completa TFS 0.3 → RevScript
ttt convert -i ./data/tfs03 -o ./output -f tfs03 -t revscript -v

# Dry-run (preview sem escrever arquivos)
ttt convert -i ./data/tfs03 -f tfs03 -t revscript --dry-run

# Com diff visual HTML
ttt convert -i ./data/tfs03 -o ./output -f tfs03 -t revscript --html-diff
```

### Lint

```bash
ttt lint ./data/scripts
ttt lint ./data/scripts --format json
ttt lint --list-rules
```

### Auto-Fix

```bash
ttt fix ./data/scripts --dry-run --diff
ttt fix ./data/scripts
```

### Análise do Servidor

```bash
ttt analyze ./data
ttt analyze ./data --format html --output analysis.html
ttt analyze ./data --only stats complexity storage
```

### Diagnóstico

```bash
ttt doctor ./data
ttt doctor ./data --format json
```

### Documentação

```bash
ttt docs ./data --format html
ttt docs ./data --format markdown
```

### Gerar Scripts

```bash
ttt create --type action --name healing_potion --format revscript
ttt create --type creaturescript --name login --format tfs1x
```

### Formatar

```bash
ttt format ./data/scripts
ttt format ./data/scripts --check
```

---

## Conversões Suportadas

| Origem | Destino | Funções | Assinaturas | Constantes | XML → RevScript | NPC |
|--------|---------|:-------:|:-----------:|:----------:|:---------------:|:---:|
| TFS 0.3.6 | TFS 1.x | 217+ | 23 | 243 | — | ✅ |
| TFS 0.3.6 | RevScript | 217+ | 23 | 243 | ✅ | ✅ |
| TFS 0.4 | TFS 1.x | 230+ | 23 | 243 | — | ✅ |
| TFS 0.4 | RevScript | 230+ | 23 | 243 | ✅ | ✅ |
| TFS 1.x | RevScript | — | — | — | ✅ | — |

### Categorias de mapeamento

| Categoria | Qtd | Exemplo |
|-----------|:---:|---------|
| Player Getters | 60+ | `getPlayerLevel(cid)` → `player:getLevel()` |
| Player Actions | 50+ | `doPlayerAddItem(cid, id, n)` → `player:addItem(id, n)` |
| Item Functions | 30+ | `doRemoveItem(uid, n)` → `Item(uid):remove(n)` |
| Game/World | 20+ | `broadcastMessage(msg)` → `Game.broadcastMessage(msg)` |
| Creature | 15+ | `doCreatureAddHealth(cid, n)` → `creature:addHealth(n)` |
| Position/Effect | 10+ | `doSendMagicEffect(pos, e)` → `pos:sendMagicEffect(e)` |
| Tile | 10+ | `getTileItemById(pos, id)` → `Tile(pos):getItemById(id)` |
| House | 8+ | `getHouseOwner(id)` → `House(id):getOwnerGuid()` |
| NPC | 10+ | `getNpcName()` → `Npc():getName()` |

O conversor marca pontos que precisam de revisão manual com comentários `-- TTT:` no código. Sempre revise esses marcadores antes de usar em produção.

---

## Linter — Regras

| Regra | Tipo | Descrição |
|-------|:----:|-----------|
| `deprecated-api` | error | Uso de funções obsoletas |
| `deprecated-constant` | warning | Constantes renomeadas |
| `invalid-callback-signature` | error | Parâmetros incorretos em callbacks |
| `missing-return` | warning | Callback sem `return true` |
| `global-variable-leak` | warning | Variável sem `local` |
| `unused-parameter` | info | Parâmetro declarado mas não usado |
| `empty-callback` | warning | Callback vazio |
| `hardcoded-id` | info | IDs numéricos hardcoded |
| `mixed-api-style` | warning | Mistura de API procedural + OOP |
| `unsafe-storage` | info | Storage keys sem constante |

---

## Auto-Fixer — Regras

| Regra | O que corrige |
|-------|--------------|
| `deprecated-api` | Chamadas procedurais → OOP |
| `deprecated-constant` | Constantes obsoletas |
| `invalid-callback-signature` | Parâmetros de callbacks |
| `missing-return` | Insere `return true` |
| `global-variable-leak` | Adiciona `local` |

---

## Analyzer — Módulos

| Módulo | Descrição |
|--------|-----------|
| `stats` | Estatísticas gerais (contagem, funções mais usadas, estilo de API) |
| `dead_code` | Scripts órfãos, referências XML quebradas, funções não utilizadas |
| `duplicates` | Scripts idênticos, registros duplicados |
| `storage` | Mapa de storage IDs, conflitos, ranges livres |
| `item_usage` | Cross-reference de item IDs entre Lua e XML |
| `complexity` | Cyclomatic complexity, nesting depth |

---

## Doctor — Verificações

| Check | Tipo | Descrição |
|-------|:----:|-----------|
| `syntax-error` | error | Erros de sintaxe Lua |
| `broken-xml-ref` | error | XMLs referenciando scripts inexistentes |
| `conflicting-id` | error | Item IDs duplicados |
| `duplicate-event` | error/warn | Eventos registrados mais de uma vez |
| `npc-duplicate-keyword` | warning | Keywords duplicadas em NPCs |
| `invalid-callback` | warning | Callbacks com assinatura inválida |

---

## Antes e Depois

<details>
<summary>Action (TFS 0.3 → RevScript)</summary>

**Antes:**
```lua
function onUse(cid, item, frompos, item2, topos)
    if getPlayerLevel(cid) < 10 then
        doPlayerSendCancel(cid, "You need level 10.")
        return TRUE
    end
    doCreatureAddHealth(cid, 200)
    doSendMagicEffect(getCreaturePosition(cid), CONST_ME_MAGIC_BLUE)
    doRemoveItem(item.uid, 1)
    return TRUE
end
```

**Depois:**
```lua
local healing_potion = Action()

function healing_potion.onUse(player, item, fromPosition, target, toPosition, isHotkey)
    if player:getLevel() < 10 then
        player:sendCancelMessage("You need level 10.")
        return true
    end
    player:addHealth(200)
    player:getPosition():sendMagicEffect(CONST_ME_MAGIC_BLUE)
    Item(item.uid):remove(1)
    return true
end

healing_potion:id(2274)
healing_potion:register()
```
</details>

<details>
<summary>CreatureScript (TFS 0.3 → RevScript)</summary>

**Antes:**
```lua
function onLogin(cid)
    local name = getCreatureName(cid)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "Welcome, " .. name .. "!")
    registerCreatureEvent(cid, "PlayerDeath")
    doPlayerSetStorageValue(cid, 50000, 1)
    return TRUE
end
```

**Depois:**
```lua
local login = CreatureEvent("PlayerLogin")

function login.onLogin(player)
    local name = player:getName()
    player:sendTextMessage(MESSAGE_STATUS_DEFAULT, "Welcome, " .. name .. "!")
    player:registerEvent("PlayerDeath")
    player:setStorageValue(50000, 1)
    return true
end

login:register()
```
</details>

---

## Configuração

### `config.toml` (Python 3.11+)

```toml
[convert]
from = "tfs03"
to = "revscript"
input = "/path/to/scripts/"
output = "/path/to/output/"
dry_run = false
html_diff = true

[lint]
format = "text"

[analyze]
only = []
format = "text"
use_ast = false

[fix]
dry_run = true
backup = true

[doctor]
format = "text"
```

Prioridade: CLI > `config.toml` > defaults.

---

## Limitações Conhecidas

| Limitação | Detalhe |
|-----------|---------|
| Funções customizadas | Funções fora da API padrão do TFS precisam de mapeamento manual |
| Metatables/closures | Tabelas Lua complexas podem precisar de revisão |
| SQL | `db.query()` e `db.storeQuery()` não são convertidos |
| Libs externas | `require()` de libs externas não é analisado |
| Marcadores `-- TTT:` | Sempre revise antes de usar em produção |
| Modo AST | Requer `luaparser`, pode falhar em sintaxe não-padrão |

---

## Nota sobre `ttt test`

O comando `ttt test` é um runner de testes para scripts OTServ baseado em `unittest`, com mocks da API TFS (`mockPlayer`, `mockCreature`, `mockItem`, `mockPosition`) e asserts customizados.

**Escopo:** `ttt test` é voltado para testar scripts de servidor, não para rodar a suite interna do TTT.

Para rodar os testes do próprio TTT:

```bash
python -m pytest tests/ -v
```

---

## Estrutura do Projeto

```
ttt/
├── main.py                    # CLI principal
├── engine.py                  # Orquestrador de conversão
├── scanner.py                 # Scanner de diretórios
├── report.py                  # Relatórios de conversão
├── diff_html.py               # Diff visual HTML
├── mappings/                  # Tabelas de mapeamento
│   ├── tfs03_functions.py     # 217 mapeamentos TFS 0.3 → 1.x
│   ├── tfs04_functions.py     # 230+ mapeamentos TFS 0.4 → 1.x
│   ├── constants.py           # 243 constantes
│   ├── signatures.py          # 23 assinaturas de callback
│   └── xml_events.py         # Definições XML → RevScript
├── converters/                # Motores de conversão
│   ├── lua_transformer.py     # Transformador regex (principal)
│   ├── ast_lua_transformer.py # Transformador AST (experimental, requer luaparser)
│   ├── xml_to_revscript.py    # XML+Lua → RevScript
│   └── npc_converter.py       # Scripts NPC
├── linter/                    # Análise estática
├── fixer/                     # Correção automática
├── analyzer/                  # Análise de servidor (6 módulos)
├── doctor/                    # Diagnóstico de saúde
├── docs/                      # Geração de documentação
├── generator/                 # Scaffolding de scripts
├── formatter/                 # Formatação Lua
└── testing/                   # Framework de testes OTServ (beta)

vscode-extension/              # Extensão VS Code (beta)
tests/                         # Suite de testes (pytest)
examples/                      # Scripts de exemplo TFS 0.3
```

---

## Testes

```bash
# Todos os testes (295 passing, 27 skipped)
python -m pytest tests/ -v

# Por módulo
python -m pytest tests/test_ttt.py -v        # Conversor
python -m pytest tests/test_linter.py -v     # Linter
python -m pytest tests/test_fixer.py -v      # Fixer
python -m pytest tests/test_analyzer.py -v   # Analyzer
python -m pytest tests/test_doctor.py -v     # Doctor
python -m pytest tests/test_formatter.py -v  # Formatter
```

Testes AST (`test_ast_*.py`) são automaticamente pulados quando `luaparser` não está instalado.

---

## Contribuindo

1. Clone e instale dependências de dev (veja [instalação](#para-desenvolvimento--contribuição))
2. Rode os testes: `python -m pytest tests/ -v`
3. Garanta lint limpo: `ruff check ttt/ tests/`
4. Abra uma issue ou envie um PR

Para adicionar novos mapeamentos de funções, edite `ttt/mappings/tfs03_functions.py` ou `tfs04_functions.py`.

---

## Licença

MIT
