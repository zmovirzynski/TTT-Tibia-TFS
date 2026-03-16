"""Shared AST utility functions for TFS Lua code conversion.

Used by both ScopeAnalyzer and ASTTransformVisitor to avoid duplication.
"""

from typing import Optional
from luaparser.astnodes import Node, Name, Index, String

# Maps obj_type strings to TFS 1.x wrapper class names.
WRAPPER_CLASSES = {
    "player": "Player",
    "creature": "Creature",
    "monster": "Monster",
    "npc": "Npc",
    "item": "Item",
    "tile": "Tile",
    "position": "Position",
}


def get_function_name(func: Node) -> Optional[str]:
    """Extract the function name from a function-call func expression.

    Args:
        func: The function expression node (Name, Index, etc.)

    Returns:
        Dot-separated name string (e.g. "Game.createItem"), or None.
    """
    if isinstance(func, Name):
        return func.id
    if isinstance(func, Index) and isinstance(func.idx, String):
        base = get_base_name(func.value)
        if base:
            s = func.idx.s
            if isinstance(s, bytes):
                s = s.decode()
            return f"{base}.{s}"
    return None


def get_base_name(node: Node) -> Optional[str]:
    """Recursively extract the leftmost Name from a (possibly nested) Index.

    Args:
        node: An AST node.

    Returns:
        The base identifier string, or None.
    """
    if isinstance(node, Name):
        return node.id
    if isinstance(node, Index):
        return get_base_name(node.value)
    return None


def get_wrapper_class(obj_type: Optional[str]) -> str:
    """Return the TFS 1.x wrapper class name for a variable type.

    Args:
        obj_type: Type string such as 'player', 'creature', etc.

    Returns:
        Class name string; defaults to 'Creature' for unknown types.
    """
    return WRAPPER_CLASSES.get(obj_type, "Creature")
