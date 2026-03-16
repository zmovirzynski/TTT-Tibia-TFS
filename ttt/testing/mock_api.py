
# Mocks para TFS API (Player, Creature, Item, Position) com suporte a AST

class MockASTNode:
    """
    Simula um nó de AST Lua para testes. Permite navegação, inspeção e modificação.
    """
    def __init__(self, node_type, value=None, children=None, **attrs):
        self.node_type = node_type  # Ex: 'function', 'call', 'table', 'var', etc.
        self.value = value
        self.children = children or []
        self.attrs = attrs

    def add_child(self, node):
        self.children.append(node)

    def find(self, node_type=None, value=None):
        """Busca recursiva por tipo/valor de nó."""
        results = []
        if (node_type is None or self.node_type == node_type) and (value is None or self.value == value):
            results.append(self)
        for child in self.children:
            results.extend(child.find(node_type, value))
        return results

    def to_dict(self):
        return {
            'type': self.node_type,
            'value': self.value,
            'children': [c.to_dict() for c in self.children],
            'attrs': self.attrs
        }

    def __repr__(self):
        return f"<ASTNode {self.node_type} value={self.value} children={len(self.children)} attrs={self.attrs}>"


class MockPlayer(MockASTNode):
    def __init__(self, name="Player", level=1, health=100, ast=None):
        super().__init__('player', value=name, children=[])
        self.level = level
        self.health = health
        self.inventory = []
        self.ast = ast or MockASTNode('player_table', value=name)

    def addItem(self, item):
        self.inventory.append(item)
        # Simula AST: adiciona item à tabela de inventário
        self.ast.add_child(MockASTNode('item', value=item))

    def getLevel(self):
        return self.level

    def isAlive(self):
        return self.health > 0

    def get_ast(self):
        return self.ast


class MockCreature(MockASTNode):
    def __init__(self, name="Creature", health=100, ast=None):
        super().__init__('creature', value=name, children=[])
        self.health = health
        self.ast = ast or MockASTNode('creature_table', value=name)

    def isAlive(self):
        return self.health > 0

    def get_ast(self):
        return self.ast


class MockItem(MockASTNode):
    def __init__(self, item_id, count=1, ast=None):
        super().__init__('item', value=item_id, children=[])
        self.count = count
        self.ast = ast or MockASTNode('item_table', value=item_id)

    def get_ast(self):
        return self.ast


class MockPosition(MockASTNode):
    def __init__(self, x, y, z, ast=None):
        super().__init__('position', value=(x, y, z), children=[])
        self.x = x
        self.y = y
        self.z = z
        self.ast = ast or MockASTNode('position_table', value=(x, y, z))

    def get_ast(self):
        return self.ast


def mockPlayer(name="Player", level=1, health=100, ast=None, **kwargs):
    return MockPlayer(name=name, level=level, health=health, ast=ast)

def mockCreature(name="Creature", health=100, ast=None, **kwargs):
    return MockCreature(name=name, health=health, ast=ast)

def mockItem(item_id, count=1, ast=None, **kwargs):
    return MockItem(item_id=item_id, count=count, ast=ast)

def mockPosition(x, y, z, ast=None, **kwargs):
    return MockPosition(x=x, y=y, z=z, ast=ast)
