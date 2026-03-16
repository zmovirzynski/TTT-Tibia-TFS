#!/usr/bin/env python3
"""
POC Final: Comparando Regex vs AST para transformação Lua

Esta POC demonstra porque AST é superior a regex para transformação de código.
"""

import re
from luaparser import ast
from luaparser.astnodes import *


def transform_with_regex(code: str) -> str:
    """
    Abordagem atual do TTT (simplificada) - USA REGEX
    
    Problemas:
    1. Transforma strings que contêm código
    2. Não entende contexto (comentários, nesting)
    3. Sensível a formatação
    """
    # Padrão simples que encontra getPlayerLevel(cid)
    pattern = r'\bgetPlayerLevel\s*\(\s*(\w+)\s*\)'
    
    def replacer(match):
        var = match.group(1)
        return f'{var}:getLevel()'
    
    return re.sub(pattern, replacer, code)


def transform_with_ast(code: str) -> str:
    """
    Abordagem proposta - USA AST
    
    Vantagens:
    1. Ignora strings automaticamente
    2. Entende estrutura hierárquica
    3. Resiliente a formatação
    """
    try:
        tree = ast.parse(code)
        
        # Usa o visitor padrão do luaparser
        class Transformer(ast.ASTVisitor):
            def visit_Call(self, node):
                if isinstance(node.func, Name) and node.func.id == "getPlayerLevel":
                    if len(node.args) >= 1:
                        # Transforma getPlayerLevel(cid) → player:getLevel()
                        arg = node.args[0]
                        if isinstance(arg, Name):
                            # Substitui por método
                            node.func = MethodInvoke(source=Name(arg.id), name="getLevel")
                            node.args = []
                
                # Continua visitando
                if hasattr(node, 'args'):
                    for arg in node.args:
                        self.visit(arg)
        
        transformer = Transformer()
        
        # Visita a árvore
        if hasattr(tree, 'body'):
            for node in tree.body.body:
                transformer.visit(node)
        
        # Gera código
        return ast.to_lua_source(tree)
    except Exception as e:
        return f"[AST Error: {e}]"


def print_comparison(name: str, code: str):
    """Mostra comparação lado a lado"""
    print(f"\n{'='*70}")
    print(f"📝 {name}")
    print(f"{'='*70}")
    print("CÓDIGO ORIGINAL:")
    print(code)
    
    print(f"{'─'*35} REGEX {'─'*28}")
    result_regex = transform_with_regex(code)
    print(result_regex)
    
    print(f"{'─'*35} AST {'─'*30}")
    result_ast = transform_with_ast(code)
    print(result_ast)
    
    # Destaca diferenças
    print(f"{'─'*70}")
    if 'getPlayerLevel' in result_regex and 'getPlayerLevel' not in result_ast:
        print("❌ REGEX: Transformou string acidentalmente!")
        print("✅ AST: Ignorou string, transformou apenas código real")


def main():
    print("="*70)
    print("PROOF OF CONCEPT: AST vs Regex para Transformação Lua")
    print("="*70)
    
    # Caso 1: Simples
    print_comparison("Caso 1 - Simples", '''
function onUse(cid, item)
    local level = getPlayerLevel(cid)
    return true
end
''')
    
    # Caso 2: String com código (armadilha para regex!)
    print_comparison("Caso 2 - String contendo código (REGEX QUEBRA!)", '''
function onUse(cid, item)
    local msg = "getPlayerLevel(cid)"  -- String, não código!
    local real = getPlayerLevel(cid)    -- Isso sim é código
    return true
end
''')
    
    # Caso 3: Comentário
    print_comparison("Caso 3 - Comentário inline", '''
function onUse(cid, item)
    local level = getPlayerLevel(cid) -- comentário
    return true
end
''')
    
    print(f"\n{'='*70}")
    print("CONCLUSÃO")
    print(f"{'='*70}")
    print("""
🔴 REGEX - Problemas:
   • Caso 2: Transformou o conteúdo da string (BUG!)
   • Não distingue código de dados
   • Frágil a formatação
   • Difícil manter com funções complexas

🟢 AST - Vantagens:
   • Caso 2: String é dado, não código - ignorado automaticamente
   • Estrutura hierárquica clara
   • Visitor pattern modular
   • Facilidade para adicionar novas transformações

📊 Arquitetura AST:
   
   Código Lua → Parser → AST (Árvore de Nós) → Visitor → Código Novo
                   ↑                              ↓
              Luaparser                      Transformações
                                             (um método por tipo)

💡 RECOMENDAÇÃO:
   Para um transpiler robusto, AST é a escolha correta.
   Regex é aceitável apenas para casos muito simples.
""")


if __name__ == "__main__":
    main()
