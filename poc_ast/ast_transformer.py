"""
Proof of Concept: Lua AST-based Transformer

Demonstra como converter código Lua TFS 0.3/0.4 para TFS 1.x/RevScript
usando Abstract Syntax Tree (AST) em vez de regex.

Vantagens:
- Resiliente a formatação (espaços, comentários)
- Entende contexto (escopo, strings vs código)
- Facilidade para lidar com nesting
- Manutenção mais simples
"""

from luaparser import ast
from luaparser.astnodes import *
from typing import Dict, List, Optional, Any, Union
import json


class TFSFunctionMapping:
    """Mapeamento de funções TFS 0.3/0.4 → TFS 1.x"""
    
    MAP = {
        # Player getters
        "getPlayerLevel": {
            "method": "getLevel",
            "obj_type": "player",
            "obj_param": 0,
            "drop_params": [0],
        },
        "getPlayerName": {
            "method": "getName", 
            "obj_type": "player",
            "obj_param": 0,
            "drop_params": [0],
        },
        "getPlayerStorageValue": {
            "method": "getStorageValue",
            "obj_type": "player",
            "obj_param": 0,
            "drop_params": [0],
        },
        
        # Player actions
        "doPlayerAddItem": {
            "method": "addItem",
            "obj_type": "player",
            "obj_param": 0,
            "drop_params": [0],
        },
        "doPlayerSendTextMessage": {
            "method": "sendTextMessage",
            "obj_type": "player",
            "obj_param": 0,
            "drop_params": [0],
        },
        "doTeleportThing": {
            "method": "teleportTo",
            "obj_type": "creature",
            "obj_param": 0,
            "drop_params": [0],
        },
        
        # Game functions
        "broadcastMessage": {
            "method": "broadcastMessage",
            "static": True,
            "static_class": "Game",
            "obj_param": None,
        },
    }


class SimpleASTTransformer(ast.ASTVisitor):
    """
    Visitor pattern para transformar AST.
    Visita cada nó e modifica conforme necessário.
    """
    
    def __init__(self):
        self.mappings = TFSFunctionMapping.MAP
        self.var_renames: Dict[str, str] = {}
        
    def transform(self, code: str) -> str:
        """Transforma código Lua completo"""
        tree = ast.parse(code)
        
        # Visita e transforma a árvore
        self.visit(tree)
        
        # Gera código de volta
        return ast.to_lua_source(tree)
    
    def visit_Call(self, node: Call):
        """Transforma chamadas de função"""
        if isinstance(node.func, Name):
            func_name = node.func.id
            
            if func_name in self.mappings:
                mapping = self.mappings[func_name]
                
                # Transforma para método OOP
                if mapping.get("static"):
                    # Game.method(...)
                    node.func = Index(
                        Name(id=mapping["static_class"]),
                        String(mapping["method"])
                    )
                else:
                    # obj:method(...)
                    obj_param = mapping.get("obj_param", 0)
                    if obj_param is not None and obj_param < len(node.args):
                        obj_arg = node.args[obj_param]
                        
                        # Aplica renomeação
                        if isinstance(obj_arg, Name) and obj_arg.id in self.var_renames:
                            obj_arg.id = self.var_renames[obj_arg.id]
                        
                        # Cria obj:method()
                        node.func = MethodInvoke(
                            source=obj_arg,
                            name=mapping["method"]
                        )
                        
                        # Remove o argumento do objeto
                        drop_params = mapping.get("drop_params", [])
                        node.args = [arg for i, arg in enumerate(node.args) 
                                    if i not in drop_params]
        
        # Continua visitando os filhos
        return self.generic_visit(node)
    
    def visit_Name(self, node: Name):
        """Renomeia variáveis"""
        if node.id in self.var_renames:
            node.id = self.var_renames[node.id]
        return node
    
    def visit_Function(self, node: Function):
        """Transforma assinatura de função"""
        # Renomeia parâmetros
        for arg in node.args:
            if isinstance(arg, Name) and arg.id in ["cid", "item", "frompos"]:
                if arg.id == "cid":
                    self.var_renames["cid"] = "player"
                    arg.id = "player"
                elif arg.id == "frompos":
                    arg.id = "fromPosition"
        
        return self.generic_visit(node)


class ASTvsRegexComparison:
    """Compara as duas abordagens"""
    
    @staticmethod
    def test_regex_approach(code: str) -> str:
        """Abordagem atual com regex (simplificada)"""
        import re
        
        # Regex simples - quebra em casos complexos!
        pattern = r'\bgetPlayerLevel\s*\(\s*(\w+)\s*\)'
        
        def replace(match):
            var = match.group(1)
            return f'{var}:getLevel()'
        
        return re.sub(pattern, replace, code)
    
    @staticmethod
    def test_ast_approach(code: str) -> str:
        """Abordagem com AST"""
        transformer = SimpleASTTransformer()
        return transformer.transform(code)


def main():
    """Demonstração da POC"""
    
    print("=" * 70)
    print("PROOF OF CONCEPT: AST-based Lua Transformer")
    print("=" * 70)
    
    # Casos de teste
    test_cases = [
        ("Caso simples", '''
function onUse(cid, item)
    local level = getPlayerLevel(cid)
    doPlayerAddItem(cid, 2160, 100)
    return TRUE
end
'''),
        
        ("Com comentários", '''
function onUse(cid, item)
    -- Pega o level do player
    local level = getPlayerLevel(cid)  -- comentário inline
    return TRUE
end
'''),
        
        ("Com strings", '''
function onUse(cid, item)
    local msg = "getPlayerLevel(cid)"  -- string, não código!
    local level = getPlayerLevel(cid)   -- isso sim é código
    return TRUE
end
'''),
        
        ("Callback NPC", '''
function creatureSayCallback(cid, type, msg)
    if getPlayerLevel(cid) < 20 then
        doPlayerSendTextMessage(cid, MESSAGE_STATUS_WARNING, "Low level!")
        return true
    end
    return false
end
'''),
    ]
    
    comparison = ASTvsRegexComparison()
    
    for name, code in test_cases:
        print(f"\n{'─' * 70}")
        print(f"📋 {name}")
        print(f"{'─' * 70}")
        print(f"📝 Original:\n{code}")
        
        # Regex (limitado)
        try:
            regex_result = comparison.test_regex_approach(code)
            print(f"🔧 Regex result:\n{regex_result}")
        except Exception as e:
            print(f"❌ Regex error: {e}")
        
        # AST
        try:
            ast_result = comparison.test_ast_approach(code)
            print(f"🌳 AST result:\n{ast_result}")
        except Exception as e:
            print(f"❌ AST error: {e}")
    
    print(f"\n{'=' * 70}")
    print("VANTAGENS DA ABORDAGEM AST:")
    print("=" * 70)
    print("""
✅ Entende estrutura do código (contexto, escopo)
✅ Ignora comentários e strings automaticamente
✅ Lida com formatação irregular (espaços, newlines)
✅ Facilidade para nesting (funções dentro de funções)
✅ Manutenção mais simples (nós vs regex complexas)
✅ Possibilidade de análise semântica (tipos, escopos)

❌ Desvantagem: Dependência de biblioteca externa (luaparser)
❌ Desvantagem: Pouco mais lento que regex simples
""")


if __name__ == "__main__":
    main()
