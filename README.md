# TTT — OTServer Developer Toolkit

> O primeiro toolkit completo para desenvolvimento OTServ.
> Converte, analisa e corrige scripts Lua e XML de versões antigas (TFS 0.3.6, TFS 0.4, TFS 1.x) para o formato **RevScript**.

[![Python 3.7+](https://img.shields.io/badge/python-3.7%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-brightgreen.svg)]()
[![Optional: luaparser](https://img.shields.io/badge/optional-luaparser-orange.svg)]()
[![Tests](https://img.shields.io/badge/tests-259%20passing-brightgreen.svg)]()

---

## Por que usar o TTT?

| Problema | Sem TTT | Com TTT |
|----------|---------|---------|
| Migrar 200+ scripts de TFS 0.3 para RevScript | Semanas de trabalho manual | **Minutos**, conversão automática |
| Aprender a nova API (OOP) | Buscar cada função no Google | O TTT já sabe 182+ mapeamentos |
| Esquecer de converter uma constante | Bugs silenciosos em produção | O TTT converte 243 constantes automaticamente |
| Saber se a conversão ficou boa | Testar script por script | **Relatório de confiança** com score por arquivo |
| Encontrar problemas nos scripts | Revisar manualmente um por um | **Linter** com 10 regras detecta tudo automaticamente |
| Corrigir API deprecated em massa | Editar cada arquivo na mão | **Auto-Fixer** corrige 5 categorias com um comando |
| Entender o estado do servidor | Nenhuma ferramenta existed | **Analyzer** gera relatorio completo (stats, dead code, storage, complexity) |
| Detectar problemas e conflitos | Testar em produção e rezar | **Doctor** diagnostica erros de sintaxe, refs quebradas, IDs conflitantes |
| Medo de perder os originais | Backups manuais, risco de sobrescrever | **Dry-run**: analisa sem tocar em nada |

---

## Funcionalidades

### Conversor (`ttt convert`)

- **182+ mapeamentos de funções** — API procedural -> OOP (`getPlayerLevel(cid)` -> `player:getLevel()`)
- **243 constantes** mapeadas automaticamente (tipos de mensagem, efeitos, slots, skulls, etc.)
- **23 assinaturas de callback** convertidas (`onUse(cid, item, ...)` -> `onUse(player, item, ...)`)
- **XML -> RevScript** — Converte actions, movements, talkactions, creaturescripts, globalevents
- **NPC Scripts** — Converte scripts de NPC (XML metadata + Lua com API antiga)
- **Diff visual (HTML)** — Página HTML interativa com diferenças lado a lado (antes/depois) via `--html-diff`. Inclui renderização on-demand, tooltips de filename e aviso de arquivos grandes
- **Relatório de conversão** — `conversion_report.txt` com estatísticas detalhadas e score de confiança
- **Conversão baseada em AST** — Usa `luaparser` para análise precisa de escopo e transformações mais confiáveis

### Linter (`ttt lint`)

- **unsafe-storage** — Storage keys sem constante definida
- **3 formatos de saída** — Text (colorido), JSON (machine-readable), HTML (relatório visual)
- **Configurável** — `.tttlint.json` para enable/disable regras por projeto

### Auto-Fixer (`ttt fix`)

- **5 regras de correção automática** — Corrige problemas detectados pelo linter
- **deprecated-api** — Substitui chamadas procedurais por OOP equivalente (182+ funções)
- **deprecated-constant** — Atualiza constantes obsoletas para os novos nomes
- **invalid-callback-signature** — Corrige parâmetros de callbacks e renomeia variáveis no corpo
- **missing-return** — Insere `return true` no final de callbacks
- **global-variable-leak** — Adiciona `local` em variáveis sem declaração
- **Modo dry-run** — Preview completo sem modificar arquivos
- **Diff antes/depois** — Visualiza exatamente o que será alterado
- **Backup automático** — Cria `.bak` antes de modificar (desativável com `--no-backup`)
- **Saída JSON** — Relatório machine-readable para integração com CI/CD

### Formatter (`ttt format`)

- **Formatação consistente de indentação** — tabs ou spaces configuráveis via `.tttformat.json`
- **Espaçamento de operadores** — Normaliza comparações e atribuições (`>=`, `==`, `=` etc.)
- **Linhas em branco entre funções** — Mantém separação previsível entre blocos
- **Alinhamento de tabelas Lua** — Alinha campos `key = value` para leitura rápida
- **Trailing commas** — Adiciona vírgulas finais em tabelas multilinha
- **Modo check para CI** — `--check` retorna erro quando há arquivos fora do padrão
- **Configuração por projeto** — Arquivo `.tttformat.json` com overrides por equipe

### Analyzer (`ttt analyze`)

- **6 módulos de análise** — Visão completa do estado do servidor
- **stats** — Total de scripts por tipo, funções mais usadas (top 15), distribuição de estilo de API (procedural/OOP)
- **dead_code** — Scripts órfãos (não referenciados em XMLs), XMLs com referências quebradas, funções definidas mas nunca chamadas
---

## Gerador de Scripts (`ttt create`)

O Script Generator permite criar rapidamente scripts prontos para RevScript (OOP) ou TFS 1.x (procedural), com templates para todos os tipos suportados. Ideal para acelerar o desenvolvimento, padronizar assinaturas e evitar erros comuns.

### Tipos suportados

| Tipo           | RevScript (OOP) | TFS 1.x (procedural) |
|----------------|-----------------|----------------------|
| Action         | ✅              | ✅                   |
| Movement       | ✅              | ✅                   |
| TalkAction     | ✅              | ✅                   |
| CreatureScript | ✅              | ✅                   |
| GlobalEvent    | ✅              | ✅                   |
| NPC            | —               | ✅                   |

### Como usar

```bash
ttt create --type action --name healing_potion --output revscript
ttt create --type creaturescript --name login --output tfs1x
ttt create --type globalevent --name startup --output revscript
```

| Parâmetro         | Descrição                                      |
|-------------------|------------------------------------------------|
| `--type`          | Tipo de script: `action`, `movement`, `talkaction`, `creaturescript`, `globalevent`, `npc` |
| `--name`          | Nome do script (ex: `healing_potion`, `login`)  |
| `--output`        | Formato: `revscript` ou `tfs1x`                |
| `--params`        | Parâmetros opcionais (ex: `--params level=10`)  |
| `--dry-run`       | Mostra o template sem salvar arquivo            |
| `--dir`           | Diretório de saída (default: atual)            |
| `--help`          | Mostra ajuda                                   |

### Exemplos

Gerar um Action para RevScript:

```bash
ttt create --type action --name healing_potion --output revscript
```

Gerar um CreatureScript para TFS 1.x:

```bash
ttt create --type creaturescript --name login --output tfs1x
```

Gerar um GlobalEvent para RevScript:

```bash
ttt create --type globalevent --name startup --output revscript
```

### Templates

Os templates gerados seguem as melhores práticas para cada formato, incluindo:
- Assinaturas corretas de callbacks
- Uso de OOP (RevScript) ou procedural (TFS 1.x)
- Comentários para facilitar customização
- Estrutura pronta para registro e uso imediato

#### Exemplo de template gerado (RevScript Action)

```lua
local healing_potion = Action()

function healing_potion.onUse(player, item, fromPosition, target, toPosition, isHotkey)
        -- Lógica customizada aqui
        return true
end

healing_potion:id(2274)
healing_potion:register()
```

#### Exemplo de template gerado (TFS 1.x CreatureScript)

```lua
function onLogin(cid)
        -- Lógica customizada aqui
        return true
end
```

---
- **duplicates** — Scripts com conteúdo idêntico, talkactions com mesma keyword, actions registradas no mesmo item ID
- **storage_scanner** — Lista todos os storage IDs usados, detecta conflitos (mesmo ID em scripts diferentes), mostra ranges livres
- **item_usage** — Item IDs referenciados em scripts e XMLs, cross-reference entre Lua e XML
- **complexity** — Cyclomatic complexity para Lua, nesting depth, sugestões de refactoring
- **3 formatos de saída** — Text (colorido), JSON (machine-readable), HTML (relatório visual)
- **Seleção de módulos** — Rode apenas os módulos que precisa com `--only`

### Doctor (`ttt doctor`)

- **6 verificações de saúde** — Diagnóstico completo do servidor
- **syntax-error** — Erros de sintaxe Lua (blocos/parênteses desbalanceados)
- **broken-xml-ref** — XMLs referenciando scripts que não existem
- **conflicting-id** — Item IDs duplicados em actions/movements
- **duplicate-event** — Eventos registrados mais de uma vez (talkactions, creature events)
- **npc-duplicate-keyword** — Keywords duplicadas em scripts de NPC
- **invalid-callback** — Callbacks com número errado de parâmetros
- **Validador XML** — Verifica XML bem-formado, atributos obrigatórios, paths de script
- **Health Score** — Score 0-100 com classificação HEALTHY / WARNING / CRITICAL
- **3 formatos de saída** — Text (colorido), JSON (machine-readable), HTML (relatório visual)

### Geral

- **Modo dry-run** — Analisa scripts sem escrever arquivos (preview seguro)
- **Zero dependências obrigatórias** — Usa apenas a biblioteca padrão do Python (luaparser opcional para modo AST)
- **Cross-platform** — Windows, Linux, macOS
- **259 testes unitários** — Cobertura completa de conversão, linter, fixer, analyzer e doctor

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

- Python 3.7+ (Python 3.11+ recomendado para suporte a `config.toml`)
- `luaparser` (opcional, para modo AST com análise de escopo)

## Instalação

```bash
git clone https://github.com/zmovirzynski/TTT-Tibia-TFS-Transpiler.git
cd TTT-Tibia-TFS-Transpiler

# (Opcional) Instalar luaparser para modo AST
pip install luaparser
```

Ou como pacote:

```bash
pip install -e .
ttt  # executa o conversor
```

---

## Configuração via Arquivo (`config.toml`)

O TTT suporta configuração via arquivo TOML (requer Python 3.11+). Coloque um arquivo `config.toml` na raiz do projeto ou use `config.example.toml` como template:

```toml
[convert]
from = "tfs03"
to = "revscript"
input = "/path/to/your/tfs/scripts/"
output = "/path/to/your/converted/scripts/"
dry_run = false
html_diff = true
verbose = true

[lint]
disable = []
format = "text"

[analyze]
only = []
format = "text"
use_ast = false

[fix]
dry_run = true
backup = false

[doctor]
format = "text"

[docs]
format = "text"
serve = false
port = 8080
```

**Prioridade:** CLI arguments > `config.toml` > valores padrão.

## Comandos Make (Makefile)

O projeto inclui um `Makefile` com comandos comuns:

```bash
make convert    # Executa conversão usando config.toml
make lint p=./data/scripts       # Executa linter
make fix p=./data/scripts        # Executa auto-fixer
make analyze p=./data            # Análise completa
make doctor p=./data             # Health check
make docs p=./data               # Gera documentação
make test                        # Roda testes
make help                        # Ajuda
```

## Uso Rápido

### Modo Interativo (Wizard)

```bash
python run.py
```

O wizard guia passo a passo: versão de origem, destino, pastas de entrada/saída e opção de dry-run.

### Converter Scripts (`ttt convert`)

```bash
# Conversão completa
ttt convert -i ./data/tfs03 -o ./output -f tfs03 -t revscript -v

# Dry-run (apenas análise, sem escrever arquivos)
ttt convert -i ./data/tfs03 -f tfs03 -t revscript --dry-run

# Gerar página HTML com diff visual (antes/depois)
ttt convert -i ./data/tfs03 -o ./output -f tfs03 -t revscript --html-diff
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

### Analisar Scripts (`ttt lint`)

```bash
# Analisar todos os scripts de um diretório
ttt lint ./data/scripts

# Saída em JSON (para integração com CI/CD)
ttt lint ./data/scripts --format json

# Gerar relatório HTML visual
ttt lint ./data/scripts --format html --output report.html

# Desabilitar regras específicas
ttt lint ./data/scripts --disable deprecated-api --disable hardcoded-id

# Listar todas as regras disponíveis
ttt lint --list-rules
```

| Parâmetro | Descrição |
|-----------|-----------|
| `path` | Arquivo ou diretório para analisar |
| `--format` | Formato de saída: `text` (padrão), `json`, `html` |
| `-o, --output` | Salvar relatório em arquivo |
| `--disable` | Desabilitar regra(s) específica(s) |
| `--enable` | Habilitar apenas regra(s) específica(s) |
| `--no-color` | Desabilitar cores no terminal |
| `-v, --verbose` | Mostrar detalhes extras |
| `--list-rules` | Listar todas as regras disponíveis e sair |

#### Regras do Linter

| Regra | Severidade | Descrição |
|-------|:----------:|-----------|
| `deprecated-api` | error | Uso de funções obsoletas (ex: `getPlayerLevel`) |
| `deprecated-constant` | warning | Constantes renomeadas ou removidas |
| `invalid-callback-signature` | error | Parâmetros incorretos em callbacks |
| `missing-return` | warning | Callback sem `return true` no final |
| `global-variable-leak` | warning | Variável sem `local` poluindo escopo global |
| `unused-parameter` | info | Parâmetro declarado mas não utilizado |
| `empty-callback` | warning | Callback vazio (sem lógica) |
| `hardcoded-id` | info | IDs numéricos hardcoded (magic numbers) |
| `mixed-api-style` | warning | Mistura de API antiga com OOP |
| `unsafe-storage` | info | Storage keys sem constante definida |

#### Exemplo de saída

```
  healing_potion.lua
    L1   [ERR] deprecated-api: 'getPlayerLevel' is deprecated, use OOP
    L3   [ERR] deprecated-api: 'doPlayerSendCancel' is deprecated, use OOP
    L6   [ERR] deprecated-api: 'doCreatureAddHealth' is deprecated, use OOP
    L7   [ERR] deprecated-api: 'doSendMagicEffect' is deprecated, use OOP
    L8   [ERR] deprecated-api: 'doRemoveItem' is deprecated, use OOP

  5 issues in 1 file (5 errors, 0 warnings, 0 info)
```

### Analisar Servidor (`ttt analyze`)

```bash
# Análise completa do servidor
ttt analyze ./data

# Saída em JSON
ttt analyze ./data --format json --output analysis.json

# Gerar relatório HTML visual
ttt analyze ./data --format html --output analysis.html

# Rodar apenas módulos específicos
ttt analyze ./data --only stats complexity storage_scanner

# Sem cores no terminal
ttt analyze ./data --no-color

# Listar módulos disponíveis
ttt analyze --list-modules
```

| Parâmetro | Descrição |
|-----------|----------|
| `path` | Diretório do servidor para analisar |
| `--format` | Formato de saída: `text` (padrão), `json`, `html` |
| `-o, --output` | Salvar relatório em arquivo |
| `--only` | Rodar apenas módulo(s) específico(s) |
| `--no-color` | Desabilitar cores no terminal |
| `-v, --verbose` | Mostrar detalhes extras |
| `--list-modules` | Listar todos os módulos disponíveis e sair |

#### Módulos do Analyzer

| Módulo | Descrição |
|--------|----------|
| `stats` | Estatísticas gerais (contagem de scripts, funções mais usadas, estilo de API) |
| `dead_code` | Scripts órfãos, referências XML quebradas, funções não utilizadas |
| `duplicates` | Scripts idênticos, registros duplicados (mesma keyword/itemid) |
| `storage_scanner` | Mapa de storage IDs, conflitos, ranges livres |
| `item_usage` | Cross-reference de item IDs entre Lua e XML |
| `complexity` | Cyclomatic complexity, nesting depth, sugestões de refactoring |

#### Exemplo de saída

```
$ ttt analyze ./data

  SERVER ANALYSIS REPORT
  ============================================================

  STATISTICS
  ----------------------------------------------------------
  Lua files:       42      XML files:     18
  Total lines:   3,421     Code lines:  2,890
  Functions:       156

  Scripts by type:
    Actions:          28   Movements:        15
    TalkActions:      12   CreatureScripts:   8
    GlobalEvents:      4   Spells:           22

  Top functions:
    player:addItem()            89 calls
    player:sendTextMessage()    76 calls
    player:getLevel()           54 calls

  STORAGE MAP
  ----------------------------------------------------------
  Unique IDs: 23    Range: 10001 - 50099
  Conflicts:  2
    ID 50001: quest1.lua, quest2.lua

  COMPLEXITY
  ----------------------------------------------------------
  Avg complexity: 4.2 (LOW)
  Distribution: 120 LOW | 28 MEDIUM | 6 HIGH | 2 VERY HIGH

  0 issues found.
```

### Diagnosticar Servidor (`ttt doctor`)

```bash
# Diagnóstico completo do servidor
ttt doctor ./data

# Saída em JSON
ttt doctor ./data --format json --output health.json

# Gerar relatório HTML visual
ttt doctor ./data --format html --output health.html

# Listar checks disponíveis
ttt doctor --list-checks
```

| Parâmetro | Descrição |
|-----------|----------|
| `path` | Diretório do servidor para diagnosticar |
| `--format` | Formato de saída: `text` (padrão), `json`, `html` |
| `-o, --output` | Salvar relatório em arquivo |
| `--no-color` | Desabilitar cores no terminal |
| `-v, --verbose` | Mostrar detalhes extras |
| `--list-checks` | Listar verificações disponíveis e sair |

#### Verificações de Saúde

| Check | Severidade | Descrição |
|-------|:----------:|----------|
| `syntax-error` | error | Erros de sintaxe Lua (blocos/parênteses desbalanceados) |
| `broken-xml-ref` | error | XMLs referenciando scripts inexistentes |
| `conflicting-id` | error | Item IDs duplicados em actions/movements |
| `duplicate-event` | error/warn | Eventos duplicados (keywords, creature events) |
| `npc-duplicate-keyword` | warning | Keywords tratadas mais de uma vez no NPC |
| `invalid-callback` | warning | Callbacks com número errado de parâmetros |
| `xml-malformed` | error | XML com erro de parse |
| `xml-missing-attr` | warning | Atributos obrigatórios ausentes |
| `xml-missing-script` | error | Script referenciado não existe no disco |

#### Health Score

| Score | Rating | Significado |
|:-----:|--------|------------|
| 90-100 | HEALTHY | Servidor em bom estado |
| 60-89 | WARNING | Alguns problemas precisam de atenção |
| 0-59 | CRITICAL | Problemas sérios detectados |

#### Exemplo de saída

```
$ ttt doctor ./data

  TTT Server Health Check
  ============================================================

  Health Score: 78/100  [!!] WARNING

  ERRORS (4)
  ----------------------------------------------------------
    [ERR] actions/scripts/old_quest.lua
          Missing 1 'end' statement(s)
    [ERR] actions/actions.xml:L45
          Script 'missing.lua' not found
    [ERR] movements/movements.xml:L12
          Duplicate movement-itemid ID 1945
    [ERR] talkactions/talkactions.xml:L8
          Duplicate talkaction keyword '!info'

  WARNINGS (3)
  ----------------------------------------------------------
    [WRN] scripts/action.lua:L1
          Callback 'onUse' has 0 params, expected at least 5
    [WRN] npc/scripts/trader.lua:L2
          NPC keyword 'trade' handled multiple times
    [WRN] talkactions.xml:L3
          Missing attribute 'words'

  SUMMARY
  ----------------------------------------------------------
    Files scanned: 42
    Errors:   4
    Warnings: 3
    XML files valid: 5/7
```

### Corrigir Scripts (`ttt fix`)

```bash
# Corrigir todos os problemas fixáveis
ttt fix ./data/scripts

# Preview — ver o que seria alterado sem modificar arquivos
ttt fix ./data/scripts --dry-run

# Mostrar diff (antes/depois) de cada alteração
ttt fix ./data/scripts --dry-run --diff

# Corrigir sem criar backups
ttt fix ./data/scripts --no-backup

# Aplicar apenas regras específicas
ttt fix ./data/scripts --only deprecated-api deprecated-constant

# Saída em JSON
ttt fix ./data/scripts --format json --output report.json
```

| Parâmetro | Descrição |
|-----------|-----------|
| `path` | Arquivo ou diretório para corrigir |
| `--dry-run` | Preview sem modificar arquivos |
| `--diff` | Mostrar diff unificado das alterações |
| `--no-backup` | Não criar arquivo `.bak` de backup |
| `--only` | Aplicar apenas regras específicas |
| `--format` | Formato de saída: `text` (padrão), `json` |
| `-o, --output` | Salvar relatório em arquivo |
| `--no-color` | Desabilitar cores no terminal |
| `-v, --verbose` | Mostrar arquivos sem alterações |

#### Regras do Auto-Fixer

| Regra | O que corrige | Exemplo |
|-------|--------------|---------|
| `deprecated-api` | Chamadas procedurais -> OOP | `getPlayerLevel(cid)` -> `player:getLevel()` |
| `deprecated-constant` | Constantes obsoletas | `TALKTYPE_ORANGE_1` -> `TALKTYPE_MONSTER_SAY` |
| `invalid-callback-signature` | Parâmetros de callbacks | `onUse(cid, item, ...)` -> `onUse(player, item, ...)` |
| `missing-return` | Callbacks sem retorno | Insere `return true` antes do `end` final |
| `global-variable-leak` | Variáveis sem `local` | `count = 0` -> `local count = 0` |

#### Exemplo de saída

```
  TTT Auto-Fixer Report
  ============================================================
  Mode: DRY RUN (no files modified)

  healing_potion.lua ............... 8 fixes
    [deprecated-api] L1: getPlayerLevel -> player:getLevel()
    [deprecated-api] L3: doPlayerSendCancel -> player:sendCancelMessage()
    [deprecated-api] L6: doCreatureAddHealth -> player:addHealth()
    [deprecated-api] L7: doSendMagicEffect -> :sendMagicEffect()
    [deprecated-api] L8: doRemoveItem -> Item(uid):remove()
    [invalid-callback-signature] L1: Updated onUse signature

  Summary: 8 files analyzed, 82 total fixes
    deprecated-api: 61 fixes
    deprecated-constant: 16 fixes
    invalid-callback-signature: 5 fixes
```

### Formatar Scripts (`ttt format`)

```bash
# Formatar todos os scripts Lua do diretório
ttt format ./data/scripts

# Rodar em modo check (não altera arquivos; ideal para CI)
ttt format ./data/scripts --check

# Forçar tabs na indentação
ttt format ./data/scripts --indent-style tabs

# Usar arquivo de configuração explícito
ttt format ./data/scripts --config .tttformat.json
```

| Parâmetro | Descrição |
|-----------|-----------|
| `path` | Arquivo ou diretório para formatar |
| `--check` | Apenas verifica; retorna exit code 1 se houver mudanças pendentes |
| `--config` | Caminho para arquivo `.tttformat.json` |
| `--indent-style` | Override: `spaces` ou `tabs` |
| `--indent-size` | Override do tamanho da indentação em spaces |

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

**Recursos do diff HTML:**
- **Renderização on-demand** — Arquivos grandes são renderizados sob demanda para evitar lag
- **Tooltips de filename** — Passe o mouse sobre os nomes de arquivo no sidebar para ver o caminho completo
- **Aviso de arquivos grandes** — Alerta quando há arquivos que podem causar lentidão

Também funciona em modo dry-run: `--dry-run --html-diff`

---

## Limitações Conhecidas

| Limitação | Detalhes |
|-----------|----------|
| Modo AST requer luaparser | Instale `pip install luaparser` para análise de escopo e transformações mais precisas |
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
├── Makefile                # Comandos comuns (convert, lint, fix, test)
├── config.example.toml     # Template de configuração (Python 3.11+)
├── .tttlint.json           # Configuração do linter (regras, severidades)
├── ttt/
│   ├── __init__.py         # Versão e metadados
│   ├── main.py             # CLI interativa + subcomandos (convert, lint, fix)
│   ├── engine.py           # Orquestrador de conversão
│   ├── scanner.py          # Scanner de diretórios com auto-detecção
│   ├── utils.py            # Utilitários (parser de args Lua, I/O)
│   ├── report.py           # Gerador de relatórios de conversão
│   ├── diff_html.py        # Gerador de diff visual HTML
│   ├── mappings/
│   │   ├── tfs03_functions.py   # 182 mapeamentos TFS 0.3 -> 1.x
│   │   ├── tfs04_functions.py   # 204 mapeamentos TFS 0.4 -> 1.x
│   │   ├── constants.py         # 243 constantes (tipos, efeitos, etc.)
│   │   ├── signatures.py        # 23 assinaturas de callback
│   │   └── xml_events.py        # Definições XML -> RevScript
│   ├── converters/
│   │   ├── ast_lua_transformer.py  # Transformador principal (AST-based, requer luaparser)
│   │   ├── lua_transformer.py      # Transformador regex (fallback)
│   │   ├── xml_to_revscript.py     # Conversor XML+Lua -> RevScript
│   │   └── npc_converter.py        # Conversor de scripts NPC
│   ├── linter/
│   │   ├── __init__.py          # Exports do módulo linter
│   │   ├── engine.py            # Motor de análise (LintEngine)
│   │   ├── rules.py             # 10 regras de lint
│   │   └── reporter.py          # Formatadores (text, JSON, HTML)
│   ├── fixer/
│   │   ├── __init__.py          # Exports do módulo fixer
│   │   └── auto_fix.py          # Motor de correção automática (5 regras)
│   └── analyzer/
│       ├── __init__.py          # Exports do módulo analyzer
│       ├── engine.py            # Motor de análise (AnalyzeEngine)
│       ├── stats.py             # Estatísticas gerais do servidor
│       ├── dead_code.py         # Detector de código morto
│       ├── duplicates.py        # Detector de duplicatas
│       ├── storage_scanner.py   # Scanner de storage IDs
│       ├── item_usage.py        # Análise de uso de item IDs
│       └── complexity.py        # Cyclomatic complexity para Lua
│   └── doctor/
│       ├── __init__.py          # Exports do módulo doctor
│       ├── engine.py            # Motor de diagnóstico (DoctorEngine)
│       ├── health_check.py      # 6 verificações de saúde
│       └── xml_validator.py     # Validador XML (3 checks)
├── tests/
│   ├── test_ttt.py          # 49 testes do conversor
│   ├── test_linter.py       # 70 testes do linter
│   ├── test_fixer.py        # 54 testes do fixer
│   ├── test_analyzer.py     # 43 testes do analyzer
│   └── test_doctor.py       # 43 testes do doctor
├── examples/
│   └── tfs03_input/         # Scripts de exemplo TFS 0.3
└── poc_ast/                 # Provas de conceito AST (exemplos/experimentos)
```

---
## Testes

```bash
# Rodar todos os testes (259 testes)
python -m pytest tests/ -v

# Apenas testes do conversor
python -m pytest tests/test_ttt.py -v

# Apenas testes do linter
python -m pytest tests/test_linter.py -v

# Apenas testes do fixer
python -m pytest tests/test_fixer.py -v
---
## Features

- [x] Script conversion (TFS 0.3/0.4/1.x/RevScript)
- [x] Linter (static analysis)
- [x] Auto fixer
- [x] Analyzer & Doctor
- [x] Docs generator (HTML/MD/JSON)
- [x] Script generator (scaffolding)
- [x] Formatter (Lua Prettier)
- [ ] Server migrator
- [x] NPC conversation analyzer
- [x] Test framework (experimental)
    - [x] Mocks de API: `mockPlayer`, `mockCreature`, `mockItem`, `mockPosition`
    - [x] Runner integrado ao CLI: `ttt test ./tests`
    - [x] Asserts customizados para cenários OTServ
- [x] VS Code extension (MVP)
    - [x] Autocomplete para `player:`, `creature:`, `item:`
    - [x] Hover docs para métodos da API TFS
    - [x] Diagnostics com integração ao `ttt lint`
    - [x] Quick fix para auto fix via `ttt fix`
    - [x] Snippets RevScript e comandos `TTT:*`

## Usage

# Apenas testes do analyzer
python -m pytest tests/test_analyzer.py -v

# Apenas testes do doctor
python -m pytest tests/test_doctor.py -v
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
