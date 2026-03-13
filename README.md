# TTT — TFS Script Converter

> Conversor universal de scripts para The Forgotten Server (TFS).
> Converte scripts Lua e XML de versões antigas (TFS 0.3.6, TFS 0.4, TFS 1.x) para o formato **RevScript**.

[![Python 3.7+](https://img.shields.io/badge/python-3.7%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)]()

---

## Por que usar o TTT?

| Problema | Sem TTT | Com TTT |
|----------|---------|---------|
| Migrar 200+ scripts de TFS 0.3 para RevScript | Semanas de trabalho manual | **Minutos**, conversão automática |
| Aprender a nova API (OOP) | Buscar cada função no Google | O TTT já sabe 182+ mapeamentos |
| Esquecer de converter uma constante | Bugs silenciosos em produção | O TTT converte 243 constantes automaticamente |
| Saber se a conversão ficou boa | Testar script por script | **Relatório de confiança** com score por arquivo |
| Medo de perder os originais | Backups manuais, risco de sobrescrever | **Dry-run**: analisa sem tocar em nada |

---

## Funcionalidades

- **182+ mapeamentos de funções** — API procedural → OOP (`getPlayerLevel(cid)` → `player:getLevel()`)
- **243 constantes** mapeadas automaticamente (tipos de mensagem, efeitos, slots, skulls, etc.)
- **23 assinaturas de callback** convertidas (`onUse(cid, item, ...)` → `onUse(player, item, ...)`)
- **XML → RevScript** — Converte actions, movements, talkactions, creaturescripts, globalevents
- **NPC Scripts** — Converte scripts de NPC (XML metadata + Lua com API antiga)
- **Diff visual (HTML)** — Página HTML interativa com diferenças lado a lado (antes/depois) via `--html-diff`
- **Relatório de conversão** — `conversion_report.txt` com estatísticas detalhadas e score de confiança
- **Modo dry-run** — Analisa scripts sem escrever arquivos (preview seguro)
- **Zero dependências** — Usa apenas a biblioteca padrão do Python
- **Cross-platform** — Windows, Linux, macOS

---

## Tabela de Compatibilidade

### Conversões suportadas

| Origem | Destino | API Lua | Assinaturas | Constantes | XML → RevScript | NPC Scripts |
|--------|---------|:-------:|:-----------:|:----------:|:---------------:|:-----------:|
| TFS 0.3.6 | TFS 1.x | ✅ 182 funções | ✅ 23 callbacks | ✅ 243 constantes | ❌ | ✅ |
| TFS 0.3.6 | RevScript | ✅ 182 funções | ✅ 23 callbacks | ✅ 243 constantes | ✅ 5 tipos XML | ✅ |
| TFS 0.4 | TFS 1.x | ✅ 204 funções | ✅ 23 callbacks | ✅ 243 constantes | ❌ | ✅ |
| TFS 0.4 | RevScript | ✅ 204 funções | ✅ 23 callbacks | ✅ 243 constantes | ✅ 5 tipos XML | ✅ |
| TFS 1.x | RevScript | — | — | — | ✅ 5 tipos XML | — |

### Tipos XML convertidos para RevScript

| Tipo | XML de entrada | Classe RevScript | Callbacks |
|------|---------------|------------------|-----------|
| Actions | `actions.xml` | `Action()` | `onUse` |
| Movements | `movements.xml` | `MoveEvent()` | `onStepIn`, `onStepOut`, `onEquip`, `onDeEquip`, `onAddItem` |
| TalkActions | `talkactions.xml` | `TalkAction()` | `onSay` |
| CreatureScripts | `creaturescripts.xml` | `CreatureEvent()` | `onLogin`, `onLogout`, `onDeath`, `onKill`, `onThink` |
| GlobalEvents | `globalevents.xml` | `GlobalEvent()` | `onStartup`, `onShutdown`, `onRecord`, `onThink`, `onTime` |
| **NPC Scripts** | `npc/*.xml` + `npc/scripts/*.lua` | (NpcHandler) | `creatureSayCallback`, `onCreatureAppear`, `onThink` |

### Categorias de funções mapeadas

| Categoria | Quantidade | Exemplos |
|-----------|:----------:|---------|
| Player Getters | 60+ | `getPlayerLevel` → `player:getLevel()` |
| Player Actions | 50+ | `doPlayerAddItem` → `player:addItem()` |
| Item Functions | 30+ | `doRemoveItem` → `Item(uid):remove()` |
| Game/World Functions | 20+ | `broadcastMessage` → `Game.broadcastMessage()` |
| Creature Functions | 15+ | `doCreatureAddHealth` → `creature:addHealth()` |
| NPC Functions | 10+ | `getNpcName` → `Npc():getName()`, `selfMoveTo` → `Npc():move()` |

---

## Requisitos

- Python 3.7+

## Instalação

```bash
git clone https://github.com/your-username/TTT-Tibia-TFS-Transpiler.git
cd TTT-Tibia-TFS-Transpiler
```

Ou como pacote:

```bash
pip install -e .
ttt  # executa o conversor
```

---

## Uso Rápido

### Modo Interativo (Wizard)

```bash
python run.py
```

O wizard guia passo a passo: versão de origem, destino, pastas de entrada/saída e opção de dry-run.

### Modo CLI

```bash
# Conversão completa
python run.py -i ./data/tfs03 -o ./output -f tfs03 -t revscript -v

# Dry-run (apenas análise, sem escrever arquivos)
python run.py -i ./data/tfs03 -f tfs03 -t revscript --dry-run

# Gerar página HTML com diff visual (antes/depois)
python run.py -i ./data/tfs03 -o ./output -f tfs03 -t revscript --html-diff
```

| Parâmetro | Descrição |
|-----------|-----------|
| `-i, --input` | Pasta com os scripts originais |
| `-o, --output` | Pasta para os scripts convertidos (opcional com `--dry-run`) |
| `-f, --from` | Versão de origem: `tfs03`, `tfs04`, `tfs1x` |
| `-t, --to` | Versão de destino: `tfs1x`, `revscript` |
| `-v, --verbose` | Modo detalhado |
| `--dry-run` | Analisa sem escrever arquivos (preview) |
| `--html-diff` | Gera página HTML com diff visual lado a lado |

---

## Antes e Depois

### Action (TFS 0.3 → RevScript)

<details>
<summary>📄 Healing Potion — clique para expandir</summary>

**Antes (TFS 0.3.6):**

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

**Depois (RevScript):**

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

### CreatureScript (TFS 0.3 → RevScript)

<details>
<summary>📄 Player Login — clique para expandir</summary>

**Antes (TFS 0.3.6):**

```lua
function onLogin(cid)
    local playerName = getCreatureName(cid)
    local playerLevel = getPlayerLevel(cid)

    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "Welcome, " .. playerName .. "!")

    if playerLevel < 8 then
        doPlayerSendTextMessage(cid, MESSAGE_EVENT_ADVANCE, "You are still a rookie!")
    end

    if isPremium(cid) then
        doPlayerSendTextMessage(cid, MESSAGE_INFO_DESCR, "Your premium account is active.")
    end

    registerCreatureEvent(cid, "PlayerDeath")
    doPlayerSetStorageValue(cid, 50000, 1)
    return TRUE
end
```

**Depois (RevScript):**

```lua
local login = CreatureEvent("PlayerLogin")

function login.onLogin(player)
    local playerName = player:getName()
    local playerLevel = player:getLevel()

    player:sendTextMessage(MESSAGE_STATUS_DEFAULT, "Welcome, " .. playerName .. "!")

    if playerLevel < 8 then
        player:sendTextMessage(MESSAGE_EVENT_ADVANCE, "You are still a rookie!")
    end

    if player:isPremium() then
        player:sendTextMessage(MESSAGE_INFO_DESCR, "Your premium account is active.")
    end

    player:registerEvent("PlayerDeath")
    player:setStorageValue(50000, 1)
    return true
end

login:register()
```

</details>

### GlobalEvent (TFS 0.3 → RevScript)

<details>
<summary>📄 Server Startup — clique para expandir</summary>

**Antes (TFS 0.3.6):**

```lua
function onStartup()
    broadcastMessage("Server is now online!", MESSAGE_STATUS_WARNING)
    setGlobalStorageValue(50001, os.time())
    print("[ServerStart] Server initialized at " .. os.date())
    return TRUE
end
```

**Depois (RevScript):**

```lua
local startup = GlobalEvent("ServerStart")

function startup.onStartup()
    Game.broadcastMessage("Server is now online!", MESSAGE_STATUS_WARNING)
    Game.setStorageValue(50001, os.time())
    print("[ServerStart] Server initialized at " .. os.date())
    return true
end

startup:register()
```

</details>

### NPC Script (TFS 0.3 → TFS 1.x)

<details>
<summary>📄 Travel NPC — clique para expandir</summary>

**Antes (TFS 0.3.6):**

```lua
function creatureSayCallback(cid, type, msg)
    if not npcHandler:isFocused(cid) then
        return false
    end

    if msgcontains(msg, "travel") then
        if getPlayerLevel(cid) < 20 then
            selfSay("You need level 20 to travel.", cid)
            return true
        end

        if doPlayerRemoveMoney(cid, 100) then
            doTeleportThing(cid, {x=1000, y=1000, z=7})
            doSendMagicEffect(getCreaturePosition(cid), CONST_ME_TELEPORT)
            selfSay("Here we go!", cid)
        end
    end

    if msgcontains(msg, "name") then
        selfSay("My name is " .. getNpcName() .. ".", cid)
    end

    return true
end
```

**Depois (TFS 1.x):**

```lua
function creatureSayCallback(cid, type, msg)
    if not npcHandler:isFocused(cid) then
        return false
    end

    if msgcontains(msg, "travel") then
        if Player(cid):getLevel() < 20 then
            selfSay("You need level 20 to travel.", cid)
            return true
        end

        if Player(cid):removeMoney(100) then
            Player(cid):teleportTo(Position(1000, 1000, 7))
            Player(cid):getPosition():sendMagicEffect(CONST_ME_TELEPORT)
            selfSay("Here we go!", cid)
        end
    end

    if msgcontains(msg, "name") then
        selfSay("My name is " .. Npc():getName() .. ".", cid)
    end

    return true
end
```

</details>

---

## Relatório de Conversão

Após cada conversão, o TTT gera automaticamente um arquivo `conversion_report.txt` com:

- **Estatísticas gerais**: arquivos convertidos, funções mapeadas, constantes substituídas
- **Score de confiança por arquivo**: HIGH (≥95%), MEDIUM (≥75%), LOW (≥50%), REVIEW (<50%)
- **Lista de pontos que precisam revisão**: marcados com `-- TTT:` no código
- **Chamadas não reconhecidas**: funções que podem precisar de mapeamento manual

### Exemplo de relatório

```
╔══════════════════════════════════════════════════════════╗
║              TTT — CONVERSION REPORT                     ║
╚══════════════════════════════════════════════════════════╝

  SUMMARY
  ─────────────────────────────────────────
  Total files analyzed:         42
  Successfully converted:       40
  Files with errors:            2
  Points needing review:        5
  Estimated confidence:         93% (HIGH)

  PER-FILE BREAKDOWN
  ─────────────────────────────────────────
  [HIGH ] healing_potion.lua      — 8 changes, 0 warnings
  [HIGH ] teleport_scroll.lua     — 12 changes, 0 warnings
  [MED  ] custom_spell.lua        — 6 changes, 1 warning
  [LOW  ] complex_quest.lua       — 3 changes, 4 warnings
```

### Modo Dry-Run

```bash
python run.py -i ./data -f tfs03 -t revscript --dry-run
```

Gera a mesma análise **sem escrever nenhum arquivo**. Ideal para:
- Avaliar a complexidade da migração antes de executar
- Identificar scripts que precisarão de ajuste manual
- Apresentar um relatório de viabilidade para a equipe

---

## Diff Visual (HTML)

```bash
python run.py -i ./data -o ./output -f tfs03 -t revscript --html-diff
```

Gera uma página HTML standalone (`conversion_diff.html`) com:
- **Sidebar de navegação** — Lista todos os arquivos com badges de status
- **Diff lado a lado** — Código original à esquerda, convertido à direita
- **Highlighting por palavra** — Diferenças destacadas dentro de cada linha
- **Filtros** — Mostrar todos, apenas alterados, ou sem mudanças
- **Estatísticas** — Total de arquivos, funções convertidas, confiança
- **Dark theme** — Interface inspirada no GitHub, pronta para uso

O HTML é 100% self-contained (zero dependências externas). Basta abrir no navegador.

Também funciona em modo dry-run: `--dry-run --html-diff`

---

## Limitações Conhecidas

| Limitação | Detalhes |
|-----------|----------|
| Não é um parser Lua completo | Usa regex com tratamento de strings/comentários — cobre 95%+ dos casos reais |
| Funções customizadas do servidor | Funções que não fazem parte da API padrão do TFS precisam de ajuste manual |
| Lógica complexa em tabelas | Tabelas Lua com metatabelas ou closures complexos podem precisar de revisão |
| SQL / banco de dados | Queries `db.query()` e `db.storeQuery()` não são convertidas |
| Módulos/bibliotecas externas | `require()` de libs externas não são analisados |
| Marcadores `-- TTT:` | Pontos que precisam de atenção manual são sinalizados no código — **sempre revise antes de usar em produção** |

---

## Estrutura do Projeto

```
TTT-Tibia-TFS-Transpiler/
├── run.py                  # Ponto de entrada
├── setup.py                # Configuração do pacote
├── ttt/
│   ├── __init__.py         # Versão e metadados
│   ├── main.py             # CLI interativa + argparse
│   ├── engine.py           # Orquestrador de conversão
│   ├── scanner.py          # Scanner de diretórios com auto-detecção
│   ├── utils.py            # Utilitários (parser de args Lua, I/O)
│   ├── report.py           # Gerador de relatórios de conversão
│   ├── diff_html.py        # Gerador de diff visual HTML
│   ├── mappings/
│   │   ├── tfs03_functions.py   # 182 mapeamentos TFS 0.3 → 1.x
│   │   ├── tfs04_functions.py   # 204 mapeamentos TFS 0.4 → 1.x
│   │   ├── constants.py         # 243 constantes (tipos, efeitos, etc.)
│   │   ├── signatures.py        # 23 assinaturas de callback
│   │   └── xml_events.py        # Definições XML → RevScript
│   └── converters/
│       ├── lua_transformer.py   # Motor de transformação Lua
│       ├── xml_to_revscript.py  # Conversor XML+Lua → RevScript
│       └── npc_converter.py     # Conversor de scripts NPC
├── tests/
│   └── test_ttt.py         # Testes unitários
└── examples/
    └── tfs03_input/         # Scripts de exemplo TFS 0.3
```

---

## Testes

```bash
python -m pytest tests/test_ttt.py -v
```

---

## Contribuindo

Contribuições são bem-vindas! Se você encontrar uma função não mapeada ou um bug:

1. Abra uma **issue** descrevendo o problema
2. Ou envie um **pull request** com o fix/mapeamento

Para adicionar novos mapeamentos, edite os arquivos em `ttt/mappings/`.

---

## Licença

MIT
