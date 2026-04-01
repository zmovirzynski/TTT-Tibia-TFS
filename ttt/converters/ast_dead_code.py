"""Scope-aware unused local variable and function detection via AST."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

try:
    from luaparser import ast as _lua_ast
    from luaparser.astnodes import (
        Node,
        Name,
        LocalAssign,
        Function,
        AnonymousFunction,
    )

    _LUAPARSER_AVAILABLE = True
except ImportError:
    _LUAPARSER_AVAILABLE = False


@dataclass
class UnusedLocal:
    name: str
    kind: str  # "variable" or "function"
    scope_level: int
    defined_at_line: Optional[int] = None


def find_unused_locals(code: str) -> List[UnusedLocal]:
    """Return locals defined but never read within their owning scope.

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

    tracker = _UsageTracker()
    tracker.visit(tree)
    return tracker.unused()


class _ScopeFrame:
    """Tracks definitions and reads within one lexical scope."""

    def __init__(self, level: int) -> None:
        self.level = level
        self.defined: Dict[str, tuple] = {}  # name → (kind, line)
        self.read: Set[str] = set()

    def define(self, name: str, kind: str, line: Optional[int] = None) -> None:
        self.defined[name] = (kind, line)

    def mark_read(self, name: str) -> None:
        self.read.add(name)

    def unused(self) -> List[UnusedLocal]:
        result = []
        for name, (kind, line) in self.defined.items():
            if name not in self.read:
                result.append(
                    UnusedLocal(
                        name=name,
                        kind=kind,
                        scope_level=self.level,
                        defined_at_line=line,
                    )
                )
        return result


class _UsageTracker:
    """Iterative AST walker that tracks local definitions and reads."""

    def __init__(self) -> None:
        self._stack: List[_ScopeFrame] = []
        self._completed: List[_ScopeFrame] = []

    def visit(self, root) -> None:
        class _Pop:
            pass

        # Push a top-level scope for module-level locals
        self._push_scope()
        work = [(root, False, False)]  # (node, post, is_local_assign_target)
        while work:
            item, post, is_target = work.pop()

            if isinstance(item, _Pop):
                if self._stack:
                    completed = self._stack.pop()
                    self._completed.append(completed)
                continue

            if item is None:
                continue

            node_type = item.__class__.__name__ if hasattr(item, "__class__") else ""

            # LocalFunction: define the name, then push a new scope for the body
            if node_type == "LocalFunction":
                name_node = getattr(item, "name", None)
                if isinstance(name_node, Name):
                    self._define(
                        name_node.id, "function", getattr(name_node, "line", None)
                    )
                elif isinstance(name_node, str):
                    self._define(name_node, "function", None)
                # Push new scope for function body
                self._push_scope()
                work.append((_Pop(), False, False))
                self._push_children(item, work, skip_attr="name")
                continue

            # Function nodes push a new scope (but not LocalFunction — handled above)
            is_func = isinstance(item, (Function, AnonymousFunction))
            if is_func:
                self._push_scope()
                work.append((_Pop(), False, False))
                self._push_children(item, work)
                continue

            # LocalAssign: targets are definitions, values are reads
            if isinstance(item, LocalAssign):
                targets = getattr(item, "targets", []) or []
                values = getattr(item, "values", []) or []

                # Push value expressions onto work stack (they are reads)
                for val in reversed(values):
                    work.append((val, False, False))

                # Determine kind per target
                for i, target in enumerate(targets):
                    if isinstance(target, Name):
                        val = values[i] if i < len(values) else None
                        is_fn = isinstance(val, (Function, AnonymousFunction)) or (
                            val is not None
                            and val.__class__.__name__ == "LocalFunction"
                        )
                        kind = "function" if is_fn else "variable"
                        self._define(target.id, kind, getattr(target, "line", None))
                continue

            # Name node — it's a read
            if isinstance(item, Name):
                self._mark_read(item.id)
                continue

            # Everything else — push children
            if isinstance(item, Node):
                self._push_children(item, work)
            elif isinstance(item, list):
                for child in reversed(item):
                    work.append((child, False, False))

        # Pop the top-level scope
        if self._stack:
            completed = self._stack.pop()
            self._completed.append(completed)

    def unused(self) -> List[UnusedLocal]:
        result: List[UnusedLocal] = []
        for frame in self._completed:
            result.extend(frame.unused())
        return result

    def _push_scope(self) -> None:
        self._stack.append(_ScopeFrame(level=len(self._stack)))

    def _define(self, name: str, kind: str, line: Optional[int]) -> None:
        if self._stack:
            self._stack[-1].define(name, kind, line)

    def _mark_read(self, name: str) -> None:
        # Mark read only in the innermost scope that defines this name.
        # This prevents shadowed outer locals from being falsely marked as read.
        for frame in reversed(self._stack):
            if name in frame.defined:
                frame.mark_read(name)
                return
        # Name not defined in any local scope — it's a global, ignore.

    def _push_children(self, node, work: list, skip_attr: Optional[str] = None) -> None:
        for attr in reversed(list(node.__dict__.keys())):
            if attr.startswith("_"):
                continue
            if skip_attr and attr == skip_attr:
                continue
            child = getattr(node, attr)
            if isinstance(child, Node):
                work.append((child, False, False))
            elif isinstance(child, list):
                work.append((child, False, False))
