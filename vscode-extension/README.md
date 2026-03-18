# TTT OTServ VS Code Extension (MVP)

Extension scaffold para OTServ com integração ao TTT.

## Recursos implementados

- Autocomplete de métodos para `player:`, `creature:`, `item:` em arquivos Lua.
- Hover docs para métodos conhecidos da API TFS.
- Diagnostics em save usando `ttt lint --format json`.
- Quick fix para chamar `TTT: Auto Fix File` quando houver diagnóstico TTT.
- Snippets RevScript para Action, TalkAction e CreatureEvent.
- Comandos:
  - `TTT: Convert File`
  - `TTT: Lint File`
  - `TTT: Generate Script`
  - `TTT: Analyze Server`
  - `TTT: Auto Fix File`

## Como usar

1. Abra a pasta `vscode-extension` no VS Code.
2. Rode `npm install` e `npm run build`.
3. Pressione `F5` para abrir o Extension Development Host.

## Fluxo para usuário leigo (instalar e usar)

1. Instalar a extensão no VS Code.
2. Abrir a pasta do servidor OT no VS Code.
3. Rodar `TTT: Primeira Configuração` no Command Palette.
4. Escolher `Runtime automático (sem Python)`.
5. A extensão baixa e configura o runtime standalone automaticamente.
6. Usar os comandos `TTT:*` sem precisar de terminal.

Na primeira ativação a extensão também mostra um prompt para configurar automaticamente.

## Instalação direta do runtime

Se quiser instalar manualmente depois, rode:

- `TTT: Instalar Runtime Automático`

Após isso, o modo padrão vira `embedded` e os comandos não dependem mais de Python.

## API custom do servidor (autocomplete/hover)

Use um arquivo JSON no workspace para colocar comandos/metodos custom do seu servidor.

- Path default: `.ttt-server-api.json`
- Comando para criar/abrir: `TTT: Criar/Abrir Config API do Servidor`

Estrutura:

- `objects`: métodos por objeto (ex: `player`, `guildSystem`)
- `globals`: funções globais custom
- `aliases`: apelidos para inferencia de tipo no autocomplete

Exemplo:

```json
{
  "objects": {
    "player": [
      {
        "method": "sendVipAlert",
        "detail": "player:sendVipAlert(title, text)",
        "description": "Envia alerta custom VIP para o jogador."
      }
    ]
  },
  "globals": [
    {
      "method": "isDoubleLootWeekend",
      "detail": "isDoubleLootWeekend() -> boolean",
      "description": "Retorna true quando o evento estiver ativo."
    }
  ],
  "aliases": {
    "p": "player"
  }
}
```

## Configurações

- `ttt.pythonCommand`: comando Python (default: `python`).
- `ttt.runPyPath`: caminho relativo para `run.py` (default: `run.py`).
- `ttt.lintOnSave`: habilita lint automático ao salvar arquivos Lua.
