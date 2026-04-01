# PO Roadmap - Top Tier Vision - 2026-04-01

## Contexto

O TTT ja passou da fase de "projeto promissor". O nucleo do toolkit existe, esta melhor documentado e ja cobre os fluxos mais importantes:

- conversao
- lint
- fix
- analyze
- doctor
- docs
- create
- format
- test framework beta
- extensao VS Code beta

Isso muda o jogo do roadmap.

O proximo passo nao e mais "ter features". O proximo passo e transformar o TTT no produto mais forte, mais confiavel e mais desejavel do ecossistema OTServ.

---

## Tese de produto

O TTT deve evoluir de "developer toolkit" para "modernization platform" de OTServ.

Em termos praticos, um TTT top de linha deve conseguir:

- migrar um servidor inteiro com seguranca
- explicar cada mudanca importante
- detectar risco antes da producao
- encaixar no fluxo do editor, da equipe e do CI
- escalar para servidores reais grandes
- ser extensivel para forks e customizacoes do ecossistema

---

## O que significa "top de linha"

Para este projeto, "top de linha" significa atingir 6 niveis ao mesmo tempo:

1. Melhor conversao do nicho
2. Melhor experiencia de migracao fim a fim
3. Melhor confianca de release e regressao
4. Melhor experiencia de uso para dev individual
5. Melhor integracao com editor e pipeline
6. Melhor extensibilidade para comunidades e equipes

Se o TTT atingir esses 6 niveis, ele deixa de ser "uma ferramenta boa" e vira referencia.

---

## North Star

North Star do produto:

"Pegar um servidor legado de TFS, rodar um fluxo guiado, sair com codigo modernizado, riscos classificados, docs geradas, diff revisavel e um plano claro do que ainda precisa de mao humana."

---

## Metas de produto

### Meta 1 - Migracao de servidor como fluxo unico

Hoje o produto tem varias pecas fortes. O proximo salto e empacotar isso como experiencia unificada.

Capacidade alvo:

- um comando principal para migracao fim a fim
- backup/snapshot antes da execucao
- convert + fix + analyze + doctor + docs numa pipeline
- relatorio final com severidade, score e proximos passos
- rollback facil

Comando alvo:

- `ttt migrate-server`

Esse comando deve virar o grande "hero flow" do produto.

### Meta 2 - Conversao com nivel industrial

Nao basta converter "bem". O TTT precisa converter melhor que qualquer abordagem manual comum.

Capacidades alvo:

- AST-first onde houver ganho real
- mapeamentos mais profundos para APIs antigas e forks comuns
- classificacao de confianca por transformacao
- justificativa de conversao por regra aplicada
- fila de review para tudo que sobrar como `-- TTT:`

Comandos e recursos alvo:

- `ttt convert --explain`
- `ttt review`
- `ttt benchmark`

### Meta 3 - Qualidade mensuravel e regressao controlada

Projeto top de linha precisa de placar objetivo.

Capacidades alvo:

- corpus de benchmark real por tipo de servidor
- goldens de entrada/saida
- metricas de cobertura de mappings
- comparativo entre versoes do TTT
- CI em Windows e Linux
- release notes baseadas em benchmark

Sem isso, o projeto cresce, mas nao prova que esta melhorando.

### Meta 4 - DX premium

Se o TTT quiser virar ferramenta favorita de time, ele precisa ser gostoso de usar.

Capacidades alvo:

- `ttt init` para scaffolding do projeto
- perfis por workspace
- watch mode para lint/fix/docs
- output HTML muito mais forte para review
- mensagens mais guiadas e menos "ferramenta crua"
- onboarding de 5 minutos

### Meta 5 - Editor-first workflow

A extensao VS Code ja existe. O proximo passo e ela deixar de ser "MVP legal" e virar vantagem competitiva.

Capacidades alvo:

- language intelligence para API TFS
- code actions orientadas a conversao
- diagnostics do `doctor` e do `analyze` dentro do editor
- preview de diff e fix sem sair do editor
- navigator de `-- TTT:` markers
- grafo de dependencias e registros

### Meta 6 - Plataforma extensivel

OTServ tem muito fork, custom API e regra de casa. O TTT precisa abracar isso.

Capacidades alvo:

- packs de mappings customizados por projeto
- packs de regras de lint/fix
- plugin API para analyzers e generators
- manifests por servidor/fork
- override facil sem fork do TTT

Se o TTT fizer isso bem, ele ganha efeito de ecossistema.

---

## Novos blocos de produto recomendados

## 1. Server Migrator

Objetivo:

- transformar o toolkit num workflow completo

Features:

- `ttt migrate-server`
- snapshot antes da execucao
- etapas selecionaveis (`convert`, `fix`, `analyze`, `doctor`, `docs`)
- checkpoints e retomada
- rollback
- export final de relatorio executivo

Valor:

- maior historia de produto da stack
- facil de vender, demonstrar e adotar

## 2. Review Workbench

Objetivo:

- reduzir friccao do que ainda precisa de revisao humana

Features:

- `ttt review`
- agregador de todos os `-- TTT:`
- agrupamento por tipo de problema
- severidade e urgencia
- snippets antes/depois
- sugestao de remediacao
- export para markdown/html/json

Valor:

- fecha o gap entre conversao automatica e trabalho humano

## 3. Benchmark and Regression Lab

Objetivo:

- medir qualidade de verdade

Features:

- `ttt benchmark`
- corpus oficial por cenarios
- score de cobertura de conversao
- score de review residual
- score de risco por release
- goldens comparativos

Valor:

- cria confianca
- guia roadmap com dados
- ajuda release e marketing tecnico

## 4. Config and Workspace System

Objetivo:

- fazer o TTT encaixar em projetos reais e equipes

Features:

- `ttt init`
- `ttt.project.toml`
- profiles por tipo de servidor
- presets para TFS 0.3, 0.4, 1.x, RevScript, forks custom
- packs locais de mappings e regras

Valor:

- reduz setup manual
- melhora onboarding
- abre caminho para plugin ecosystem

## 5. HTML Dashboard 2.0

Objetivo:

- transformar output em experiencia de review e gestao

Features:

- dashboard unico de migracao
- cards de risco
- tabela de arquivos com filtros
- diff com razao da mudanca
- painel de markers `-- TTT:`
- scorecards por modulo
- graficos de regressao entre execucoes

Valor:

- deixa a ferramenta muito mais vendavel
- ajuda tanto dev quanto PO/tech lead

## 6. VS Code Pro

Objetivo:

- levar o TTT para dentro do fluxo diario do desenvolvedor

Features:

- code action "Convert this file"
- code action "Apply safe fixes"
- painel de migration review
- preview de docs geradas
- diagnostics integrados
- navegacao entre XML e script
- coverage de API TFS/forks

Valor:

- cria uso recorrente
- aumenta lock-in positivo do produto

## 7. Plugin / Rules Ecosystem

Objetivo:

- deixar o TTT adaptavel ao mundo real do OTServ

Features:

- SDK para mappings customizados
- SDK para rules de lint/fix
- SDK para analyzers
- formato estavel para plugins
- registry simples de community packs

Valor:

- expande alcance do produto sem explodir o core

---

## Priorizacao recomendada

## Fase A - Hero Flow

Objetivo:

- transformar o produto em "uma experiencia", nao so um conjunto de comandos

Entradas:

- `ttt migrate-server`
- `ttt review`
- dashboard HTML 2.0

Impacto:

- altissimo

## Fase B - Quality Moat

Objetivo:

- fazer o TTT provar que e melhor a cada release

Entradas:

- `ttt benchmark`
- corpus oficial
- CI multi-platform
- regressao comparativa por release

Impacto:

- altissimo

## Fase C - Editor and Team Workflow

Objetivo:

- ganhar uso diario e recorrente

Entradas:

- VS Code Pro
- `ttt init`
- project manifest
- presets por workspace

Impacto:

- alto

## Fase D - Ecosystem

Objetivo:

- virar plataforma extensivel, nao so app fechado

Entradas:

- plugin API
- community packs
- rules/mappings customizados por projeto

Impacto:

- alto e estrategico

## Fase E - Advanced Intelligence

Objetivo:

- empurrar o TTT para frente do mercado

Entradas:

- explicacao de transformacoes
- cadeias de impacto entre arquivos
- sugestoes guiadas para review residual
- assistencia opcional baseada em AST e heuristicas do projeto

Impacto:

- diferenca competitiva forte

---

## Roadmap proposto

## Roadmap 1 - Proxima wave

Foco:

- `ttt migrate-server`
- `ttt review`
- dashboard HTML 2.0
- CI basico

Entrega esperada:

- TTT passa de toolkit para plataforma de migracao

## Roadmap 2 - Prova de qualidade

Foco:

- `ttt benchmark`
- corpus oficial
- score de cobertura e score de review residual
- changelog de benchmark por release

Entrega esperada:

- TTT passa a provar melhoria em vez de so prometer

## Roadmap 3 - Uso diario

Foco:

- VS Code Pro
- `ttt init`
- project manifest
- presets e profiles

Entrega esperada:

- TTT passa a ser usado no dia a dia e nao so em migracao

## Roadmap 4 - Ecossistema

Foco:

- plugin API
- mappings packs
- rules packs
- analyzers customizados

Entrega esperada:

- TTT ganha tracao de comunidade e vira referencia de nicho

---

## Novos comandos que fariam o produto subir de patamar

- `ttt migrate-server`
- `ttt review`
- `ttt benchmark`
- `ttt init`
- `ttt explain`
- `ttt profile`
- `ttt plugin`

---

## KPIs recomendados

Se o projeto quer ser top de linha, precisa medir.

KPIs sugeridos:

- tempo medio para migrar um servidor exemplo
- quantidade media de `-- TTT:` por 100 arquivos convertidos
- cobertura de mappings por corpus real
- taxa de sucesso de benchmark por release
- tempo de onboarding de novo contribuidor
- numero de code actions usadas na extensao
- tempo medio para sair de legacy para reviewable output

---

## O que nao priorizar agora

Para nao perder foco, eu nao priorizaria neste momento:

- web SaaS separado
- suporte a linguagens fora do escopo TFS/Lua/XML
- features sociais/comunitarias antes do plugin system
- mais comandos pequenos e isolados sem costura de experiencia

---

## Decisao de PO recomendada

Se eu estivesse tocando isso como PO, a mensagem seria:

"A base ficou boa. Agora o TTT precisa virar o produto que organiza a migracao inteira, mede qualidade de forma objetiva e cria uma experiencia premium para devs e times."

Em ordem:

1. Hero flow de migracao
2. Benchmark e quality moat
3. VS Code e workflow de equipe
4. Plugin ecosystem
5. Inteligencia avancada

Esse e o caminho para o TTT virar top de linha de verdade, e nao so um toolkit forte.
