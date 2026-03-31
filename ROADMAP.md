# TTT Roadmap

> Histórico de desenvolvimento e direção atual do projeto.

---

## Status Atual (Março 2026)

O TTT evoluiu de um "script converter" para um toolkit completo. O foco atual é **estabilidade, confiança e qualidade de conversão** — não novas features grandes.

### Prioridades ativas

1. **Confiabilidade** — baseline de testes verde, CLI sem crashes, AST seguro
2. **Qualidade de conversão** — reduzir marcadores `-- TTT:` manuais, fechar mappings pendentes
3. **Documentação honesta** — README e docs alinhados com a realidade
4. **Consolidação** — amadurecer módulos beta, resolver ambiguidades arquiteturais

### Novas frentes grandes estão congeladas até as prioridades acima estarem resolvidas.

---

## Módulos — Status de Maturidade

| Módulo | Status | Próximo passo |
|--------|:------:|---------------|
| `convert` | **Stable** | Continuar fechando mappings pendentes |
| `lint` | **Stable** | — |
| `fix` | **Stable** | — |
| `analyze` | **Stable** | Endurecer `--use-ast` quando luaparser instalado |
| `doctor` | **Stable** | — |
| `docs` | **Stable** | — |
| `create` | **Stable** | — |
| `format` | **Beta** | Testes adicionais em corpus real |
| `test` | **Beta** | Definir escopo: runner OTServ vs suite interna |
| AST transform | **Experimental** | Mais testes, melhor fallback |
| VS Code ext | **Beta** | Adicionar test suite TypeScript |
| NPC Analyzer | **Stub** | Decidir: implementar ou remover do código |
| Server Migrator | **Backlog** | Só após estabilização do núcleo |

---

## Backlog priorizado

### P0 — Confiabilidade ✅ (concluído Março 2026)

- [x] Baseline de testes verde (295 passing, 27 skipped)
- [x] `ttt lint --list-rules` funciona sem path
- [x] `ttt lint` não crasheia no Windows (encoding fallback)
- [x] `--use-ast` não gera falsos positivos sem luaparser
- [x] `semantic_duplicates` incluído em JSON/métricas
- [x] Testes AST pulam graciosamente sem luaparser
- [x] `requirements.txt` com dependências de dev

### P1 — Qualidade de conversão ✅ (concluído Março 2026)

- [x] Mappings pendentes fechados (182 → 217+)
- [x] `doSendAnimatedText` tratado corretamente (note-only)
- [x] Estratégia para `getTileInfo` (note-only com guidance)
- [x] Town/Guild/Vocation chain unwrapping validado
- [x] Corpus de regressão com 19 testes

### P1 — Clareza de produto ✅ (concluído Março 2026)

- [x] README reescrito sem overclaim
- [x] Matriz de maturidade por módulo
- [x] Dependências opcionais documentadas
- [x] ROADMAP transformado em histórico + direção
- [x] Features experimentais/stub marcadas

### P2 — Consolidação de módulos experimentais ✅ (concluído Março 2026)

- [x] NPC Analyzer marcado como stub no README (não exposto no CLI)
- [x] `ttt test` escopo definido: runner OTServ, não suite interna
- [x] `ttt/analyzers/` consolidado (renomeado para `ttt/converters/analysis/` ou mantido como interno)
- [x] VS Code extension marcada como beta

### P3 — Futuro (não iniciado)

- [ ] Server Migrator (`ttt migrate-server`)
- [ ] Automações de modernização guiadas por AST
- [ ] Relatórios comparativos entre releases/conversões
- [ ] Melhorias avançadas na extensão VS Code
- [ ] Suite de testes TypeScript para a extensão
- [ ] CI/CD pipeline

---

## Histórico de Fases

As fases abaixo documentam a evolução do projeto. Todas estão implementadas exceto onde indicado.

### Fase 1 — Linter (`ttt lint`) ✅

10 regras de análise estática, 3 formatos de saída (text, JSON, HTML), configuração via `.tttlint.json`.

### Fase 2 — Auto-Fixer (`ttt fix`) ✅

5 regras de correção automática, dry-run, diff, backup automático.

### Fase 3 — Analyzer + Doctor (`ttt analyze` / `ttt doctor`) ✅

6 módulos de análise (stats, dead_code, duplicates, storage, item_usage, complexity). Doctor com 6+3 checks e health score.

### Fase 4 — Docs Generator (`ttt docs`) ✅

Geração automática de documentação em HTML, Markdown e JSON. Servidor local com `--serve`.

### Fase 5 — Script Generator (`ttt create`) ✅

Scaffolding para action, movement, talkaction, creaturescript, globalevent, npc. Formatos RevScript e TFS 1.x.

### Fase 6 — Formatter (`ttt format`) ✅

Indentação, espaçamento, alinhamento de tabelas, trailing commas. Modo `--check` para CI.

### Fase 7 — Server Migrator ⬜

Planejado. Migração completa combinando convert + analyze + doctor. Não implementado.

### Fase 8 — NPC Conversation Analyzer ⬜

Stub criado em `ttt/analyzer/npc_analyzer.py`. Sem implementação real. Sem integração ao CLI.

### Fase 9 — Test Framework (`ttt test`) ✅

Runner unittest com mocks OTServ (mockPlayer, mockCreature, mockItem, mockPosition) e asserts customizados.

### Fase 10 — VS Code Extension ✅ (beta)

Autocomplete, hover docs, diagnostics, quick fix, snippets, 8 comandos TTT.

---

*Última atualização: Março 2026*
