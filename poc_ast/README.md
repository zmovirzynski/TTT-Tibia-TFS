# POC: AST vs Regex para Transformação Lua

## 🎯 Objetivo

Demonstrar por que **Abstract Syntax Tree (AST)** é superior a **Regex** para transformação de código Lua no contexto do TTT (TFS Script Converter).

## 📁 Arquivos

- `final_poc.py` - Proof of concept comparando as duas abordagens
- `ast_transformer.py` - Implementação conceitual completa do transformer baseado em AST
- `simple_poc.py` - Versão simplificada para testes

## 🚀 Como Executar

```bash
cd poc_ast
python3 final_poc.py
```

## 📊 Resultado Esperado

### Caso 2: String contendo código

```lua
-- CÓDIGO ORIGINAL:
function onUse(cid, item)
    local msg = "getPlayerLevel(cid)"  -- String, não código!
    local real = getPlayerLevel(cid)    -- Isso sim é código
    return true
end

-- REGEX (QUEBRA!):
function onUse(cid, item)
    local msg = "cid:getLevel()"  -- ❌ String foi transformada!
    local real = cid:getLevel()    -- ✅ Código transformado
    return true
end

-- AST (CORRETO!):
-- String permanece inalterada, apenas código real é transformado
```

## 🔴 Problemas da Abordagem Regex

| Problema | Exemplo |
|----------|---------|
| **Strings** | `"getPlayerLevel(cid)"` → `"cid:getLevel()"` ❌ |
| **Comentários** | `-- call getPlayerLevel(cid)` pode ser afetado |
| **Formatação** | Espaços irregulares quebram padrões |
| **Nesting** | Funções aninhadas são difíceis de tratar |
| **Manutenção** | Regex complexas são ilegíveis |

## 🟢 Vantagens da Abordagem AST

```
Código Lua → Parser → AST (Árvore) → Visitor → Código Novo
                 ↓                      ↓
            Luaparser             Transformações
                                    (modular)
```

| Vantagem | Descrição |
|----------|-----------|
| **Contexto** | Sabe diferenciar código de dados (strings) |
| **Estrutura** | Entende hierarquia (funções dentro de funções) |
| **Resiliente** | Funciona com qualquer formatação |
| **Extensível** | Adicionar novas transformações é fácil |
| **Manutenção** | Código limpo e testável |

## 🏗️ Arquitetura Proposta (AST)

```python
from luaparser import ast
from luaparser.astnodes import *

class TFSVisitor(ast.ASTVisitor):
    """Cada tipo de nó tem seu método de transformação"""
    
    def visit_Function(self, node):
        """Transforma assinatura: onUse(cid) → onUse(player)"""
        pass
    
    def visit_Call(self, node):
        """Transforma chamada: getPlayerLevel(cid) → player:getLevel()"""
        pass
    
    def visit_Name(self, node):
        """Renomeia variáveis: cid → player"""
        pass

# Uso
tree = ast.parse(codigo_lua)
visitor = TFSVisitor()
visitor.visit(tree)
codigo_novo = ast.to_lua_source(tree)
```

## 📦 Dependências

```bash
pip install luaparser
```

## 💡 Recomendação

Para o TTT v2.0, recomenda-se:

1. **Migrar gradualmente** para AST
2. **Começar por funções simples** (getters/setters)
3. **Manter regex** como fallback para casos não cobertos
4. **Usar Visitor Pattern** para organizar transformações

## 🔗 Referências

- [luaparser](https://github.com/boolang/pyLuaparser) - Parser Lua para Python
- [Visitor Pattern](https://en.wikipedia.org/wiki/Visitor_pattern) - Design pattern para AST traversal
- [AST](https://en.wikipedia.org/wiki/Abstract_syntax_tree) - Conceito de Abstract Syntax Tree
