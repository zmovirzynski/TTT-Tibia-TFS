#!/usr/bin/env python3
"""
POC Simples: AST vs Regex para transformação Lua
"""

from luaparser import ast
from luaparser.astnodes import *
import re


def regex_transform(code: str) -> str:
    """
    Abordagem com Regex - FRÁGIL!
    """
    # Problema: regex não entende contexto
    
    # 1. Transforma getPlayerLevel(cid) → player:getLevel()
    # Mas quebra se tiver comentários, strings, ou formatação estranha
    code = re.sub(
        r'\bgetPlayerLevel\s*\(\s*(\w+)\s*\)',
        r'\1:getLevel()',
        code
    )
    
    # 2. Transforma doPlayerAddItem(cid, id, count) → player:addItem(id, count)
    code = re.sub(
        r'\bdoPlayerAddItem\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\)',
        r'\1:addItem(\2, \3)',
        code
    )
    
    return code


def ast_transform(code: str) -> str:
    """
    Abordagem com AST - ROBUSTA!
    """
    tree = ast.parse(code)
    
    # Visitor que transforma a AST
    class TFSVisitor(ast.ASTVisitor):
        def __init__(self):
            self.var_map = {}
        
        def visit_Function(self, node):
            """Transforma assinatura de função"""
            for i, arg in enumerate(node.args):
                if isinstance(arg, Name) and arg.id == "cid":
                    self.var_map["cid"] = "player"
                    arg.id = "player"
            # Visita filhos
            if hasattr(node, 'body'):
                for stmt in node.body:
                    self.visit(stmt)
        
        def visit_Call(self, node):
            """Transforma chamadas de função"""
            if isinstance(node.func, Name):
                # getPlayerLevel(cid) → player:getLevel()
                if node.func.id == "getPlayerLevel":
                    if len(node.args) >= 1 and isinstance(node.args[0], Name):
                        obj_name = self.var_map.get(node.args[0].id, node.args[0].id)
                        node.func = MethodInvoke(source=Name(obj_name), name="getLevel")
                        node.args = []  # Remove o cid
                
                # doPlayerAddItem(cid, itemid, count) → player:addItem(itemid, count)
                elif node.func.id == "doPlayerAddItem":
                    if len(node.args) >= 1 and isinstance(node.args[0], Name):
                        obj_name = self.var_map.get(node.args[0].id, node.args[0].id)
                        node.func = MethodInvoke(source=Name(obj_name), name="addItem")
                        node.args = node.args[1:]  # Remove o cid, mantém resto
                
                # broadcastMessage(msg, type) → Game.broadcastMessage(msg, type)
                elif node.func.id == "broadcastMessage":
                    node.func = Index(Name("Game"), String("broadcastMessage"))
            
            # Visita argumentos
            for arg in node.args:
                self.visit(arg)
        
        def visit_Name(self, node):
            """Renomeia variáveis"""
            if node.id in self.var_map:
                node.id = self.var_map[node.id]
    
    # Aplica o visitor
    visitor = TFSVisitor()
    visitor.visit(tree)
    
    # Gera código
    return ast.to_lua_source(tree)


def main():
    print("=" * 70)
    print("POC: AST vs Regex para Transformação Lua")
    print("=" * 70)
    
    # Casos de teste
    test_cases = [
        ("Caso Simples", '''
function onUse(cid, item)
    local level = getPlayerLevel(cid)
    doPlayerAddItem(cid, 2160, 100)
    return true
end
'''),
        
        ("Com String (armadilha para regex)", '''
function onUse(cid, item)
    local msg = "getPlayerLevel(cid)"  -- Isso é string, não código!
    local level = getPlayerLevel(cid)   -- Isso sim é código
    return true
end
'''),
        
        ("Comentário Inline", '''
function onUse(cid, item)
    local level = getPlayerLevel(cid) -- pega level
    doPlayerAddItem(cid, 2160, 100)
    return true
end
'''),
        
        ("Espaçamento Estranho", '''
function onUse(cid, item)
    local level = getPlayerLevel ( cid )
    doPlayerAddItem( cid , 2160 , 100 )
    return true
end
'''),
    ]
    
    for name, code in test_cases:
        print(f"\n{'─' * 70}")
        print(f"📋 {name}")
        print(f"{'─' * 70}")
        print(f"📝 ORIGINAL:\n{code}")
        
        # Regex
        print(f"🔧 REGEX:\n{regex_transform(code)}")
        
        # AST
        try:
            print(f"🌳 AST:\n{ast_transform(code)}")
        except Exception as e:
            print(f"❌ AST Error: {e}")
    
    print(f"\n{'=' * 70}")
    print("ANÁLISE:")
    print("=" * 70)
    print("""
🔴 REGEX - Problemas:
   • Caso 2 (String): Regex transforma o conteúdo da string!
   • Caso 4 (Espaçamento): Pode não capturar padrões irregulares
   • Não entende contexto (comentários, strings, nesting)

🟢 AST - Vantagens:
   • Caso 2 (String): Ignora automaticamente - é dado, não código
   • Caso 4 (Espaçamento): Funciona com qualquer formatação
   • Entende estrutura hierárquica do código
   • Manutenção: basta adicionar visitor methods

🟡 AST - Desvantagens:
   • Dependência de biblioteca (luaparser)
   • Overhead de parse + visit + generate
   • Requer entendimento de estrutura AST
""")


if __name__ == "__main__":
    main()
