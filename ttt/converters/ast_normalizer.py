"""AST structural normalization for semantic duplicate detection."""
from __future__ import annotations
import sys
from typing import List

try:
    from luaparser import ast as _lua_ast
    from luaparser.astnodes import (
        Node, Name, String, Number, TrueExpr, FalseExpr, Nil,
        Function, AnonymousFunction, LocalFunction,
        If, While, Repeat, Fornum, Forin,
        Return, Break, Assign, LocalAssign,
        Call, Invoke,
        BinaryOp, UnaryOp,
    )
    _LUAPARSER_AVAILABLE = True
except ImportError:
    _LUAPARSER_AVAILABLE = False

_V = "V"
_S = "S"
_N = "N"
_F = "F"


def normalize_ast_structure(code: str) -> str:
    if not _LUAPARSER_AVAILABLE or not code.strip():
        return ""
    old = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(5000)
        tree = _lua_ast.parse(code)
    except Exception:
        return ""
    finally:
        sys.setrecursionlimit(old)

    parts: List[str] = []
    _flatten(tree, parts)
    return " ".join(parts)


def structural_similarity(code_a: str, code_b: str) -> float:
    norm_a = normalize_ast_structure(code_a)
    norm_b = normalize_ast_structure(code_b)
    if not norm_a and not norm_b:
        return 1.0
    if not norm_a or not norm_b:
        return 0.0
    if norm_a == norm_b:
        return 1.0
    tokens_a = set(norm_a.split())
    tokens_b = set(norm_b.split())
    return len(tokens_a & tokens_b) / len(tokens_a | tokens_b)


def _flatten(node, parts: List[str]) -> None:
    if node is None:
        return
    node_type = node.__class__.__name__

    # Leaf nodes — emit placeholder and stop
    if isinstance(node, Name):
        parts.append(_V)
        return
    if isinstance(node, String):
        parts.append(_S)
        return
    if isinstance(node, Number):
        parts.append(_N)
        return
    if _LUAPARSER_AVAILABLE and isinstance(node, (TrueExpr, FalseExpr)):
        parts.append("BOOL")
        return
    if _LUAPARSER_AVAILABLE and isinstance(node, Nil):
        parts.append("NIL")
        return

    # Structural tokens
    if _LUAPARSER_AVAILABLE and isinstance(node, (Function, AnonymousFunction, LocalFunction)):
        parts.append(_F)
    elif _LUAPARSER_AVAILABLE and isinstance(node, If) or node_type in ("If", "ElseIf"):
        parts.append("IF")
    elif _LUAPARSER_AVAILABLE and isinstance(node, While):
        parts.append("WHILE")
    elif _LUAPARSER_AVAILABLE and isinstance(node, Repeat):
        parts.append("REPEAT")
    elif _LUAPARSER_AVAILABLE and isinstance(node, Fornum):
        parts.append("FORNUM")
    elif _LUAPARSER_AVAILABLE and isinstance(node, Forin):
        parts.append("FORIN")
    elif _LUAPARSER_AVAILABLE and isinstance(node, Return):
        parts.append("RETURN")
    elif _LUAPARSER_AVAILABLE and isinstance(node, Break):
        parts.append("BREAK")
    elif _LUAPARSER_AVAILABLE and isinstance(node, Call):
        parts.append("CALL")
    elif _LUAPARSER_AVAILABLE and isinstance(node, Invoke):
        parts.append("INVOKE")
    elif _LUAPARSER_AVAILABLE and isinstance(node, (Assign, LocalAssign)):
        parts.append("ASSIGN")
    elif _LUAPARSER_AVAILABLE and isinstance(node, BinaryOp):
        parts.append("BOP")
    elif _LUAPARSER_AVAILABLE and isinstance(node, UnaryOp):
        parts.append("UOP")

    # Recurse into children
    if not _LUAPARSER_AVAILABLE:
        return
    if isinstance(node, Node):
        for attr in node.__dict__:
            if attr.startswith("_"):
                continue
            child = getattr(node, attr)
            _flatten_child(child, parts)


def _flatten_child(child, parts: List[str]) -> None:
    if not _LUAPARSER_AVAILABLE:
        return
    if isinstance(child, Node):
        _flatten(child, parts)
    elif isinstance(child, list):
        for item in child:
            _flatten_child(item, parts)
