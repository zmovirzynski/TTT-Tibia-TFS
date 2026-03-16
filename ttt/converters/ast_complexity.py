"""AST-based cyclomatic complexity computation for Lua functions."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import List

try:
    from luaparser import ast as _lua_ast
    from luaparser.astnodes import (
        Node, Function, AnonymousFunction, Name,
    )
    _LUAPARSER_AVAILABLE = True
except ImportError:
    _LUAPARSER_AVAILABLE = False

_BRANCH_NODE_TYPES = {
    "If", "ElseIf",
    "While", "Repeat",
    "Fornum", "Forin",
    "And", "Or",
}

_NESTING_OPENERS = {"If", "While", "Repeat", "Fornum", "Forin"}


@dataclass
class FunctionMetrics:
    name: str
    cyclomatic: int
    nesting_depth: int
    lines: int
    rating: str = field(init=False)

    def __post_init__(self) -> None:
        if self.cyclomatic <= 5:
            self.rating = "LOW"
        elif self.cyclomatic <= 10:
            self.rating = "MEDIUM"
        elif self.cyclomatic <= 20:
            self.rating = "HIGH"
        else:
            self.rating = "VERY HIGH"


def compute_file_complexity(code: str) -> List[FunctionMetrics]:
    """Walk the AST of code and return per-function complexity metrics.

    Returns an empty list on parse failure (never raises).
    """
    if not _LUAPARSER_AVAILABLE:
        return []

    if not code.strip():
        return []

    old_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(5000)
        tree = _lua_ast.parse(code)
    except Exception:
        return []
    finally:
        sys.setrecursionlimit(old_limit)

    results: List[FunctionMetrics] = []
    _collect_functions(tree, code, results)
    return results


def _is_function_node(node) -> bool:
    return (
        isinstance(node, (Function, AnonymousFunction))
        or node.__class__.__name__ == "LocalFunction"
    )


def _collect_functions(node, code: str, results: List[FunctionMetrics]) -> None:
    if node is None:
        return

    if _is_function_node(node):
        name = _get_name(node)
        cyclomatic, max_nesting = _measure(node)
        lines = _count_lines(node)
        results.append(FunctionMetrics(
            name=name,
            cyclomatic=cyclomatic,
            nesting_depth=max_nesting,
            lines=lines,
        ))
        # Don't recurse further — nested functions get their own entry
        # by _measure skipping them, but we DO still need to visit nested functions
        # as top-level entries. So we recurse into children looking for more functions.
        _recurse_for_nested_functions(node, code, results)
        return

    if isinstance(node, Node):
        for attr in node.__dict__:
            if attr.startswith("_"):
                continue
            child = getattr(node, attr)
            _visit_child_for_collect(child, code, results)
    elif isinstance(node, list):
        for item in node:
            _collect_functions(item, code, results)


def _recurse_for_nested_functions(func_node, code: str, results: List[FunctionMetrics]) -> None:
    """Find any functions nested inside func_node and add them to results."""
    for attr in func_node.__dict__:
        if attr.startswith("_"):
            continue
        child = getattr(func_node, attr)
        _visit_child_for_collect(child, code, results)


def _visit_child_for_collect(child, code: str, results) -> None:
    if isinstance(child, Node):
        _collect_functions(child, code, results)
    elif isinstance(child, list):
        for item in child:
            if item is not None:
                _collect_functions(item, code, results)


def _measure(func_node) -> tuple:
    """Return (cyclomatic_complexity, max_nesting_depth) for a function node."""
    branches = [0]
    max_nest = [0]

    def walk(node, depth: int) -> None:
        if node is None:
            return
        node_type = node.__class__.__name__

        # Don't descend into nested function bodies (they're separate entries)
        if node is not func_node and (
            isinstance(node, (Function, AnonymousFunction))
            or node_type == "LocalFunction"
        ):
            return

        if node_type in _BRANCH_NODE_TYPES:
            branches[0] += 1

        new_depth = depth
        if node is not func_node and node_type in _NESTING_OPENERS:
            new_depth = depth + 1
            if new_depth > max_nest[0]:
                max_nest[0] = new_depth

        if isinstance(node, Node):
            for attr in node.__dict__:
                if attr.startswith("_"):
                    continue
                child = getattr(node, attr)
                _walk_child(child, new_depth, walk)

    def _walk_child(child, depth: int, walk_fn) -> None:
        if isinstance(child, Node):
            walk_fn(child, depth)
        elif isinstance(child, list):
            for item in child:
                if item is not None:
                    _walk_child(item, depth, walk_fn)

    walk(func_node, depth=0)
    return 1 + branches[0], max_nest[0]


def _get_name(node) -> str:
    name_attr = getattr(node, "name", None)
    if name_attr is None:
        return "<anonymous>"
    if isinstance(name_attr, Name):
        return name_attr.id
    if isinstance(name_attr, str):
        return name_attr
    return "<anonymous>"


def _count_lines(node) -> int:
    start = getattr(node, "line", None)
    end = getattr(node, "end_line", None)
    if start is not None and end is not None:
        return end - start + 1
    return 0
