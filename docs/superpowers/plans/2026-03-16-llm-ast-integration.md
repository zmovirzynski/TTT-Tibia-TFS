# LLM-AST Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the AST the authoritative analysis backend for all LLM-facing guidelines, replacing regex heuristics with structurally correct metrics derived from the parsed Lua AST.

**Architecture:** The `ScopeAnalyzer` and `ASTTransformVisitor` in `ttt/converters/` already parse and traverse the full Lua AST. This plan adds three new AST modules (complexity, dead code, normalizer), enriches `LuaFileAnalysis` with AST-derived data, and wires everything into `GuidelinesGenerator` so the LLM receives accurate, scope-aware context instead of regex approximations. A final task plugs the AST modules into `AnalyzeEngine` as an optional high-accuracy backend.

**Tech Stack:** Python 3.7+, `luaparser` (AST parsing), `pytest` (tests). Zero new external dependencies.

---

## Dependency Order

```
Task 1 (ast_complexity.py)
Task 2 (ast_dead_code.py)
    ↓
Task 3 (enrich LuaFileAnalysis + GuidelinesGenerator)  ← depends on 1 & 2
Task 4 (ast_normalizer.py + semantic duplicates)        ← independent
    ↓
Task 5 (wire into AnalyzeEngine)  ← depends on 1, 2, 4
```

Execute Tasks 1, 2, and 4 in any order (or in parallel). Task 3 requires 1 and 2 to be done. Task 5 requires 1, 2, and 4.

---

## Chunk 1: AST Complexity + Scope Dead Code Modules

### Task 1: AST-based Cyclomatic Complexity

**Context:**
`ttt/analyzer/complexity.py` computes cyclomatic complexity by regex-counting branch keywords (`if`, `while`, `for`, etc.). This has false positives for keywords inside strings. The AST already has every branch node typed — we just need to walk it and count.

**Files:**

- Create: `ttt/converters/ast_complexity.py`
- Test: `tests/test_ast_complexity.py`

---

- [ ] **Step 1.1: Write the failing tests**

```python
# tests/test_ast_complexity.py
import pytest
from ttt.converters.ast_complexity import compute_file_complexity, FunctionMetrics

SIMPLE_LUA = """
function onUse(player, item, fromPosition, target, toPosition)
    player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "hello")
    return true
end
"""

BRANCHY_LUA = """
function doHeal(cid, amount)
    if not isPlayer(cid) then return false end
    if amount > 100 then
        amount = 100
    elseif amount < 0 then
        amount = 0
    end
    for i = 1, amount do
        if i > 50 then break end
    end
    return true
end
"""

NESTED_LUA = """
function complex(cid)
    if isPlayer(cid) then
        for i = 1, 10 do
            if i > 5 then
                while true do
                    if i == 7 then break end
                end
            end
        end
    end
end
"""


def test_simple_function_low_complexity():
    metrics = compute_file_complexity(SIMPLE_LUA)
    assert len(metrics) == 1
    fn = metrics[0]
    assert fn.name == "onUse"
    assert fn.cyclomatic == 1  # no branches
    assert fn.nesting_depth == 0


def test_branchy_function_complexity():
    metrics = compute_file_complexity(BRANCHY_LUA)
    assert len(metrics) == 1
    fn = metrics[0]
    assert fn.name == "doHeal"
    assert fn.cyclomatic == 5  # if + if + elseif + for + if = 5 branches → base 1 + 4 = 5
    assert fn.rating in ("MEDIUM", "HIGH")


def test_nesting_depth():
    metrics = compute_file_complexity(NESTED_LUA)
    assert len(metrics) == 1
    fn = metrics[0]
    assert fn.nesting_depth >= 4


def test_multiple_functions():
    code = SIMPLE_LUA + "\n" + BRANCHY_LUA
    metrics = compute_file_complexity(code)
    assert len(metrics) == 2
    names = {m.name for m in metrics}
    assert names == {"onUse", "doHeal"}


def test_empty_file_returns_empty():
    assert compute_file_complexity("") == []


def test_fallback_on_parse_error():
    # Invalid Lua should not raise — returns empty list
    result = compute_file_complexity("function (((broken")
    assert isinstance(result, list)
```

- [ ] **Step 1.2: Run to confirm FAIL**

```bash
cd /var/home/gaamelu/development/tools/script-converter
python -m pytest tests/test_ast_complexity.py -v 2>&1 | head -30
```

Expected: `ModuleNotFoundError` or `ImportError` — `ast_complexity` doesn't exist yet.

- [ ] **Step 1.3: Implement `ttt/converters/ast_complexity.py`**

```python
"""AST-based cyclomatic complexity computation for Lua functions."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import List, Optional

_BRANCH_NODE_TYPES = {
    "If", "ElseIf",          # if / elseif
    "While", "Repeat",       # while / repeat-until
    "Fornum", "Forin",       # for i= / for k,v in
    "And", "Or",             # short-circuit logic
}

_NESTING_OPENERS = {"If", "While", "Repeat", "Fornum", "Forin", "Function", "AnonymousFunction"}


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
    """Walk the AST of ``code`` and return per-function complexity metrics.

    Returns an empty list on parse failure (never raises).
    """
    try:
        from luaparser import ast
        from luaparser.astnodes import Function, AnonymousFunction, Node
    except ImportError:
        return []

    if not code.strip():
        return []

    old_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(5000)
        tree = ast.parse(code)
    except Exception:
        return []
    finally:
        sys.setrecursionlimit(old_limit)

    results: List[FunctionMetrics] = []
    _collect_functions(tree, code, results, depth=0)
    return results


def _collect_functions(node, code: str, results: List[FunctionMetrics], depth: int) -> None:
    """Recursively visit nodes and collect FunctionMetrics for each function."""
    from luaparser.astnodes import Function, AnonymousFunction, Node

    if node is None:
        return

    if isinstance(node, (Function, AnonymousFunction)) or (
        hasattr(node, "__class__") and node.__class__.__name__ == "LocalFunction"
    ):
        name = _get_name(node)
        cyclomatic, max_nesting = _measure(node)
        lines = _count_lines(node, code)
        results.append(FunctionMetrics(
            name=name,
            cyclomatic=cyclomatic,
            nesting_depth=max_nesting,
            lines=lines,
        ))
        # Don't recurse into nested functions — they get their own entry
        return

    if isinstance(node, Node):
        for attr in node.__dict__:
            if attr.startswith("_"):
                continue
            child = getattr(node, attr)
            _visit_child(child, code, results, depth)
    elif isinstance(node, list):
        for item in node:
            _collect_functions(item, code, results, depth)


def _visit_child(child, code: str, results, depth: int) -> None:
    from luaparser.astnodes import Node
    if isinstance(child, Node):
        _collect_functions(child, code, results, depth)
    elif isinstance(child, list):
        for item in child:
            _collect_functions(item, code, results, depth)


def _measure(func_node) -> tuple[int, int]:
    """Return (cyclomatic_complexity, max_nesting_depth) for a function node."""
    branches = [0]
    max_nest = [0]

    def walk(node, depth: int) -> None:
        if node is None:
            return
        node_type = node.__class__.__name__
        if node_type in _BRANCH_NODE_TYPES:
            branches[0] += 1
        if node_type in _NESTING_OPENERS and node is not func_node:
            max_nest[0] = max(max_nest[0], depth)
            depth += 1

        from luaparser.astnodes import Node
        if isinstance(node, Node):
            for attr in node.__dict__:
                if attr.startswith("_"):
                    continue
                child = getattr(node, attr)
                _walk_child(child, depth, walk)

    def _walk_child(child, depth: int, walk_fn) -> None:
        from luaparser.astnodes import Node, Function, AnonymousFunction
        if isinstance(child, (Function, AnonymousFunction)) or (
            hasattr(child, "__class__") and child.__class__.__name__ == "LocalFunction"
        ):
            return  # don't descend into nested functions
        if isinstance(child, Node):
            walk_fn(child, depth)
        elif isinstance(child, list):
            for item in child:
                _walk_child(item, depth, walk_fn)

    walk(func_node, depth=0)
    return 1 + branches[0], max_nest[0]


def _get_name(node) -> str:
    from luaparser.astnodes import Name
    name_attr = getattr(node, "name", None)
    if name_attr is None:
        return "<anonymous>"
    if isinstance(name_attr, Name):
        return name_attr.id
    if isinstance(name_attr, str):
        return name_attr
    return "<anonymous>"


def _count_lines(node, code: str) -> int:
    """Approximate line count using AST line metadata if available."""
    start = getattr(node, "line", None)
    end = getattr(node, "end_line", None)
    if start and end:
        return end - start + 1
    return 0
```

- [ ] **Step 1.4: Run tests to confirm PASS**

```bash
python -m pytest tests/test_ast_complexity.py -v
```

Expected: all tests pass.

- [ ] **Step 1.5: Commit**

```bash
git add ttt/converters/ast_complexity.py tests/test_ast_complexity.py
git commit -m "feat: add AST-based cyclomatic complexity module"
```

---

### Task 2: Scope-Aware Dead Local Code Detection

**Context:**
`ttt/analyzer/dead_code.py` detects unused functions via text-search — it finds the function name as a string anywhere in the project. This produces false positives when different files define a function with the same name. Our `ScopeAnalyzer` already tracks scope hierarchy and variable definitions. This task extends it to also track **reads** (variable references), enabling detection of locals that are defined but never read within their scope.

**Files:**

- Create: `ttt/converters/ast_dead_code.py`
- Test: `tests/test_ast_dead_code.py`

---

- [ ] **Step 2.1: Write the failing tests**

```python
# tests/test_ast_dead_code.py
import pytest
from ttt.converters.ast_dead_code import find_unused_locals, UnusedLocal

CLEAN_LUA = """
function onUse(player, item)
    local msg = "hello"
    player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, msg)
    return true
end
"""

UNUSED_VAR_LUA = """
function doSomething(cid)
    local unused = 42
    local used = getPlayerLevel(cid)
    return used
end
"""

UNUSED_FUNC_LUA = """
local function helper()
    return 1
end

local function alsoUnused()
    return 2
end

function onLogin(player)
    return true
end
"""

USED_FUNC_LUA = """
local function helper()
    return 1
end

function onLogin(player)
    local x = helper()
    return x > 0
end
"""

SHADOWED_LUA = """
function outer(cid)
    local x = 1
    do
        local x = 2   -- shadows outer x; inner x never read
        return x
    end
    return x
end
"""


def test_clean_code_no_unused():
    result = find_unused_locals(CLEAN_LUA)
    assert result == []


def test_detects_unused_variable():
    result = find_unused_locals(UNUSED_VAR_LUA)
    names = {u.name for u in result}
    assert "unused" in names
    assert "used" not in names


def test_detects_unused_local_functions():
    result = find_unused_locals(UNUSED_FUNC_LUA)
    names = {u.name for u in result}
    assert "helper" in names
    assert "alsoUnused" in names


def test_used_local_function_not_flagged():
    result = find_unused_locals(USED_FUNC_LUA)
    names = {u.name for u in result}
    assert "helper" not in names


def test_returns_empty_on_parse_error():
    result = find_unused_locals("function (((broken")
    assert result == []


def test_unused_local_has_metadata():
    result = find_unused_locals(UNUSED_VAR_LUA)
    assert len(result) >= 1
    u = next(r for r in result if r.name == "unused")
    assert u.scope_level >= 0
    assert u.kind in ("variable", "function")
```

- [ ] **Step 2.2: Run to confirm FAIL**

```bash
python -m pytest tests/test_ast_dead_code.py -v 2>&1 | head -20
```

Expected: `ImportError` — module doesn't exist.

- [ ] **Step 2.3: Implement `ttt/converters/ast_dead_code.py`**

```python
"""Scope-aware unused local variable and function detection via AST."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class UnusedLocal:
    name: str
    kind: str           # "variable" or "function"
    scope_level: int
    defined_at_line: Optional[int] = None


def find_unused_locals(code: str) -> List[UnusedLocal]:
    """Return locals defined but never read within their owning scope.

    Returns an empty list on parse failure (never raises).
    """
    try:
        from luaparser import ast as lua_ast
        from luaparser.astnodes import (
            Node, Name, LocalAssign, Assign, Function,
            AnonymousFunction, Chunk, Block,
        )
    except ImportError:
        return []

    if not code.strip():
        return []

    old_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(5000)
        tree = lua_ast.parse(code)
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
        # name → (kind, line)
        self.defined: Dict[str, tuple[str, Optional[int]]] = {}
        self.read: Set[str] = set()

    def define(self, name: str, kind: str, line: Optional[int] = None) -> None:
        self.defined[name] = (kind, line)

    def mark_read(self, name: str) -> None:
        self.read.add(name)

    def unused(self) -> List[UnusedLocal]:
        result = []
        for name, (kind, line) in self.defined.items():
            if name not in self.read:
                result.append(UnusedLocal(
                    name=name, kind=kind,
                    scope_level=self.level, defined_at_line=line,
                ))
        return result


class _UsageTracker:
    """Iterative AST walker that tracks local variable definitions and reads."""

    def __init__(self) -> None:
        self._stack: List[_ScopeFrame] = []

    # ── Public ────────────────────────────────────────────────────────────────

    def visit(self, root) -> None:
        from luaparser.astnodes import (
            Node, Name, LocalAssign, Function, AnonymousFunction,
        )

        class _Pop:
            pass

        work = [(root, False)]
        while work:
            item, post = work.pop()

            if isinstance(item, _Pop):
                if self._stack:
                    self._stack.pop()
                continue

            if isinstance(item, (Function, AnonymousFunction)) or (
                hasattr(item, "__class__") and item.__class__.__name__ == "LocalFunction"
            ):
                self._push_scope()
                work.append((_Pop(), False))
                self._push_children(item, work)
                continue

            if isinstance(item, LocalAssign):
                self._handle_local_assign(item)
                self._push_children(item, work)
                continue

            if isinstance(item, Name):
                # Any Name reference that's NOT on the left side of a LocalAssign
                # counts as a read. We handle the definition side in LocalAssign visitor,
                # so here we always mark as read.
                if self._stack:
                    self._stack[-1].mark_read(item.id)
                    # Propagate read upward (closures can read outer scopes)
                    for frame in self._stack[:-1]:
                        frame.mark_read(item.id)
                continue

            if isinstance(item, Node):
                self._push_children(item, work)
            elif isinstance(item, list):
                for child in reversed(item):
                    work.append((child, False))

    def unused(self) -> List[UnusedLocal]:
        result: List[UnusedLocal] = []
        for frame in self._stack:
            result.extend(frame.unused())
        return result

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _push_scope(self) -> None:
        self._stack.append(_ScopeFrame(level=len(self._stack)))

    def _handle_local_assign(self, node) -> None:
        from luaparser.astnodes import Name, Function, AnonymousFunction
        if not self._stack:
            return
        frame = self._stack[-1]
        targets = getattr(node, "targets", []) or []
        values = getattr(node, "values", []) or []
        for i, target in enumerate(targets):
            if isinstance(target, Name):
                val = values[i] if i < len(values) else None
                is_func = isinstance(val, (Function, AnonymousFunction)) or (
                    val is not None and val.__class__.__name__ == "LocalFunction"
                )
                line = getattr(target, "line", None)
                frame.define(target.id, "function" if is_func else "variable", line)
                # Don't mark target as read — it's being defined

    def _push_children(self, node, work: list) -> None:
        from luaparser.astnodes import Node
        for attr in reversed(list(node.__dict__.keys())):
            if attr.startswith("_"):
                continue
            child = getattr(node, attr)
            if isinstance(child, Node):
                work.append((child, False))
            elif isinstance(child, list):
                work.append((child, False))
```

- [ ] **Step 2.4: Run tests to confirm PASS**

```bash
python -m pytest tests/test_ast_dead_code.py -v
```

Expected: all pass.

- [ ] **Step 2.5: Commit**

```bash
git add ttt/converters/ast_dead_code.py tests/test_ast_dead_code.py
git commit -m "feat: add scope-aware unused local detection via AST"
```

---

## Chunk 2: Enrich Guidelines + Semantic Duplicates

### Task 3: Enrich LuaFileAnalysis and GuidelinesGenerator with AST data

**Context:**
`LuaFileAnalysis` (in `ttt/analyzers/lua_oop_analyzer.py`) currently carries only regex-detected OOP issues. `GuidelinesGenerator` generates a per-file LLM prompt that says things like "refactor for OOP style". This task enriches both with AST-derived data: exact complexity scores, max nesting, unused locals — so the LLM prompt is precise and actionable rather than generic.

**Files:**

- Modify: `ttt/analyzers/lua_oop_analyzer.py` — add `ast_metrics` field to `LuaFileAnalysis`
- Create: `ttt/analyzers/ast_enricher.py` — orchestrates AST modules and populates `ast_metrics`
- Modify: `ttt/analyzers/guidelines_generator.py` — use AST metrics when available
- Test: `tests/test_ast_enricher.py`

---

- [ ] **Step 3.1: Write the failing tests**

```python
# tests/test_ast_enricher.py
import pytest
from ttt.analyzers.ast_enricher import enrich_analysis, ASTMetrics
from ttt.analyzers.lua_oop_analyzer import LuaFileAnalysis

COMPLEX_LUA = """
function bigFunc(cid, amount)
    if not isPlayer(cid) then return false end
    if amount > 100 then
        amount = 100
    elseif amount < 0 then
        amount = 0
    end
    for i = 1, amount do
        if i > 50 then
            doPlayerSendTextMessage(cid, 22, tostring(i))
        end
    end
    local unused = "dead"
    return true
end
"""

SIMPLE_LUA = """
function onLogin(player)
    return true
end
"""


def test_enrich_produces_metrics():
    analysis = LuaFileAnalysis(file_path="test.lua", total_lines=20)
    enriched = enrich_analysis(analysis, COMPLEX_LUA)
    assert enriched.ast_metrics is not None
    m = enriched.ast_metrics
    assert m.max_complexity >= 4
    assert m.max_nesting >= 2
    assert len(m.function_metrics) >= 1


def test_unused_locals_detected():
    analysis = LuaFileAnalysis(file_path="test.lua", total_lines=20)
    enriched = enrich_analysis(analysis, COMPLEX_LUA)
    assert enriched.ast_metrics is not None
    assert len(enriched.ast_metrics.unused_locals) >= 1
    names = {u.name for u in enriched.ast_metrics.unused_locals}
    assert "unused" in names


def test_simple_function_low_complexity():
    analysis = LuaFileAnalysis(file_path="simple.lua", total_lines=3)
    enriched = enrich_analysis(analysis, SIMPLE_LUA)
    assert enriched.ast_metrics is not None
    assert enriched.ast_metrics.max_complexity == 1


def test_enrich_returns_same_object():
    """enrich_analysis mutates and returns the same LuaFileAnalysis."""
    analysis = LuaFileAnalysis(file_path="x.lua", total_lines=5)
    result = enrich_analysis(analysis, SIMPLE_LUA)
    assert result is analysis


def test_enrich_does_not_raise_on_bad_lua():
    analysis = LuaFileAnalysis(file_path="bad.lua", total_lines=1)
    result = enrich_analysis(analysis, "function (((")
    assert result.ast_metrics is not None
    assert result.ast_metrics.max_complexity == 0
```

- [ ] **Step 3.2: Run to confirm FAIL**

```bash
python -m pytest tests/test_ast_enricher.py -v 2>&1 | head -20
```

Expected: `ImportError`.

- [ ] **Step 3.3: Add `ast_metrics` field to `LuaFileAnalysis`**

In `ttt/analyzers/lua_oop_analyzer.py`, add the import and field:

```python
# At the top, add:
from typing import Optional, TYPE_CHECKING
if TYPE_CHECKING:
    from ttt.analyzers.ast_enricher import ASTMetrics
```

Change the `LuaFileAnalysis` dataclass:

```python
@dataclass
class LuaFileAnalysis:
    file_path: str
    issues: List[LuaOopIssue] = field(default_factory=list)
    total_lines: int = 0
    ast_metrics: Optional["ASTMetrics"] = field(default=None, repr=False)
```

- [ ] **Step 3.4: Implement `ttt/analyzers/ast_enricher.py`**

```python
"""Enriches LuaFileAnalysis with AST-derived metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from ttt.analyzers.lua_oop_analyzer import LuaFileAnalysis

from ttt.converters.ast_complexity import FunctionMetrics, compute_file_complexity
from ttt.converters.ast_dead_code import UnusedLocal, find_unused_locals


@dataclass
class ASTMetrics:
    function_metrics: List[FunctionMetrics] = field(default_factory=list)
    unused_locals: List[UnusedLocal] = field(default_factory=list)

    @property
    def max_complexity(self) -> int:
        if not self.function_metrics:
            return 0
        return max(m.cyclomatic for m in self.function_metrics)

    @property
    def max_nesting(self) -> int:
        if not self.function_metrics:
            return 0
        return max(m.nesting_depth for m in self.function_metrics)

    @property
    def high_complexity_functions(self) -> List[FunctionMetrics]:
        return [m for m in self.function_metrics if m.rating in ("HIGH", "VERY HIGH")]


def enrich_analysis(analysis: "LuaFileAnalysis", code: str) -> "LuaFileAnalysis":
    """Populate ``analysis.ast_metrics`` from AST analysis of ``code``.

    Mutates and returns ``analysis``. Never raises.
    """
    fn_metrics = compute_file_complexity(code)
    unused = find_unused_locals(code)
    analysis.ast_metrics = ASTMetrics(
        function_metrics=fn_metrics,
        unused_locals=unused,
    )
    return analysis
```

- [ ] **Step 3.5: Run tests to confirm PASS**

```bash
python -m pytest tests/test_ast_enricher.py -v
```

- [ ] **Step 3.6: Update `GuidelinesGenerator` to use AST metrics**

In `ttt/analyzers/guidelines_generator.py`, update `_format_file` to emit AST-enriched context when available. Add this helper and update `_format_file`:

```python
def _format_ast_section(self, ast_metrics: "ASTMetrics") -> List[str]:
    """Emit a concise AST metrics block for the LLM prompt."""
    lines = []
    if ast_metrics.high_complexity_functions:
        lines.append("### AST Complexity (exact)")
        lines.append("")
        for fn in ast_metrics.high_complexity_functions[:5]:
            lines.append(
                f"- `{fn.name}`: cyclomatic={fn.cyclomatic} ({fn.rating}), "
                f"nesting={fn.nesting_depth}"
            )
        lines.append("")

    if ast_metrics.unused_locals:
        names = ", ".join(f"`{u.name}`" for u in ast_metrics.unused_locals[:6])
        if len(ast_metrics.unused_locals) > 6:
            names += f" (+{len(ast_metrics.unused_locals) - 6} more)"
        lines.append(f"**Unused locals:** {names}")
        lines.append("")

    return lines
```

In `_format_file`, insert after the `lua.issues` block:

```python
if lua.ast_metrics:
    lines.extend(self._format_ast_section(lua.ast_metrics))
```

And update the "Suggested LLM prompt" to include complexity info:

```python
# After building topics_str, add complexity context:
if lua.ast_metrics and lua.ast_metrics.high_complexity_functions:
    fn = lua.ast_metrics.high_complexity_functions[0]
    complexity_hint = (
        f" Focus on `{fn.name}` (complexity={fn.cyclomatic}, nesting={fn.nesting_depth}) first."
    )
else:
    complexity_hint = ""
lines.append(
    f"> Refactor `{lua.file_path}` for TFS 1.x/RevScript OOP style: "
    f"{topics_str}. Cache entity objects as locals, use method calls "
    f"instead of global functions, and handle nil player guards.{complexity_hint}"
)
```

- [ ] **Step 3.7: Write integration test for enriched guidelines**

```python
# Add to tests/test_ast_enricher.py:

from ttt.analyzers.guidelines_generator import GuidelinesGenerator

ENRICHED_LUA = """
function bigAction(cid, amount)
    if not isPlayer(cid) then return false end
    if amount > 100 then amount = 100
    elseif amount < 0 then amount = 0
    end
    for i = 1, amount do
        if i > 50 then doPlayerSendTextMessage(cid, 22, "hi") end
    end
    return true
end
"""


def test_guidelines_include_ast_complexity():
    from ttt.analyzers.lua_oop_analyzer import LuaOopAnalyzer
    from ttt.analyzers.ast_enricher import enrich_analysis

    analyzer = LuaOopAnalyzer()
    analysis = analyzer.analyze_content(ENRICHED_LUA, "action.lua")
    enrich_analysis(analysis, ENRICHED_LUA)

    gen = GuidelinesGenerator()
    output = gen.generate([analysis])

    assert "cyclomatic" in output or "complexity" in output.lower()
```

- [ ] **Step 3.8: Run all enricher + guidelines tests**

```bash
python -m pytest tests/test_ast_enricher.py -v
```

- [ ] **Step 3.9: Commit**

```bash
git add ttt/analyzers/lua_oop_analyzer.py ttt/analyzers/ast_enricher.py \
        ttt/analyzers/guidelines_generator.py tests/test_ast_enricher.py
git commit -m "feat: enrich LuaFileAnalysis and guidelines with AST complexity and dead code data"
```

---

### Task 4: Semantic Duplicate Detection via AST Normalization

**Context:**
`ttt/analyzer/duplicates.py` hashes normalized source text to detect identical scripts. This misses semantic duplicates where variable names differ but structure is identical — a common pattern in TFS scripts where the same logic is copy-pasted with renamed entity variables. This task adds AST-based structural comparison.

**Files:**

- Create: `ttt/converters/ast_normalizer.py`
- Modify: `ttt/analyzer/duplicates.py` — add `detect_semantic_duplicates()`
- Test: `tests/test_ast_normalizer.py`

---

- [ ] **Step 4.1: Write the failing tests**

```python
# tests/test_ast_normalizer.py
import pytest
from ttt.converters.ast_normalizer import normalize_ast_structure, structural_similarity

FUNC_A = """
function onUseSword(player, item, fromPosition, target, toPosition)
    local level = getPlayerLevel(player)
    if level < 50 then
        doPlayerSendTextMessage(player, 22, "Too low level")
        return false
    end
    return true
end
"""

FUNC_B = """
function onUseShield(cid, item, fromPos, target, toPos)
    local lvl = getPlayerLevel(cid)
    if lvl < 50 then
        doPlayerSendTextMessage(cid, 22, "Too low level")
        return false
    end
    return true
end
"""

FUNC_DIFFERENT = """
function onLogin(player)
    player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "Welcome!")
    return true
end
"""


def test_renamed_vars_are_structural_duplicates():
    score = structural_similarity(FUNC_A, FUNC_B)
    assert score >= 0.85, f"Expected high similarity, got {score}"


def test_different_functions_are_not_similar():
    score = structural_similarity(FUNC_A, FUNC_DIFFERENT)
    assert score < 0.5, f"Expected low similarity, got {score}"


def test_identical_code_is_100_percent_similar():
    score = structural_similarity(FUNC_A, FUNC_A)
    assert score == 1.0


def test_normalize_returns_string():
    result = normalize_ast_structure(FUNC_A)
    assert isinstance(result, str)
    assert len(result) > 0


def test_normalize_strips_variable_names():
    norm_a = normalize_ast_structure(FUNC_A)
    norm_b = normalize_ast_structure(FUNC_B)
    assert norm_a == norm_b


def test_normalize_returns_empty_string_on_parse_error():
    result = normalize_ast_structure("function (((broken")
    assert result == ""
```

- [ ] **Step 4.2: Run to confirm FAIL**

```bash
python -m pytest tests/test_ast_normalizer.py -v 2>&1 | head -20
```

- [ ] **Step 4.3: Implement `ttt/converters/ast_normalizer.py`**

```python
"""AST-based structural normalization for semantic duplicate detection.

Strips variable names, string literals, and numeric constants from the AST
to produce a canonical "shape" string. Two code snippets with the same shape
but different variable names are structurally identical.
"""

from __future__ import annotations

import sys
from typing import Optional

# Canonical placeholder tokens
_VAR = "V"
_STR = "S"
_NUM = "N"
_FUNC = "F"


def normalize_ast_structure(code: str) -> str:
    """Return a canonical shape string for ``code``.

    All variable names → ``V``, string literals → ``S``, numbers → ``N``,
    function names → ``F``. Control-flow structure is preserved exactly.

    Returns ``""`` on parse failure (never raises).
    """
    try:
        from luaparser import ast as lua_ast
        from luaparser.astnodes import Node
    except ImportError:
        return ""

    if not code.strip():
        return ""

    old_limit = sys.getrecursionlimit()
    try:
        sys.setrecursionlimit(5000)
        tree = lua_ast.parse(code)
    except Exception:
        return ""
    finally:
        sys.setrecursionlimit(old_limit)

    parts: list[str] = []
    _flatten(tree, parts)
    return " ".join(parts)


def structural_similarity(code_a: str, code_b: str) -> float:
    """Jaccard similarity of normalized AST token bags for ``code_a`` and ``code_b``."""
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
    intersection = tokens_a & tokens_b
    union = tokens_a | tokens_b
    return len(intersection) / len(union)


# ── Internal flattener ────────────────────────────────────────────────────────

def _flatten(node, parts: list[str]) -> None:
    """Walk the AST and emit structural tokens into ``parts``."""
    from luaparser.astnodes import (
        Node, Name, String, Number, TrueExpr, FalseExpr, NilExpr,
        Function, AnonymousFunction,
        If, ElseIf, While, Repeat, Fornum, Forin,
        Return, Break, Assign, LocalAssign,
        Call, Invoke, Index, Field,
        BinaryOp, UnaryOp, And, Or,
    )

    if node is None:
        return

    node_type = node.__class__.__name__

    # Structural keywords — emit as-is
    if isinstance(node, (If, ElseIf)):
        parts.append("IF")
    elif isinstance(node, While):
        parts.append("WHILE")
    elif isinstance(node, Repeat):
        parts.append("REPEAT")
    elif isinstance(node, Fornum):
        parts.append("FORNUM")
    elif isinstance(node, Forin):
        parts.append("FORIN")
    elif isinstance(node, Return):
        parts.append("RETURN")
    elif isinstance(node, Break):
        parts.append("BREAK")
    elif isinstance(node, (Function, AnonymousFunction)) or node_type == "LocalFunction":
        parts.append(_FUNC)
    elif isinstance(node, (Assign, LocalAssign)):
        parts.append("ASSIGN")
    elif isinstance(node, Call):
        parts.append("CALL")
    elif isinstance(node, Invoke):
        parts.append("INVOKE")
    elif isinstance(node, (And, Or)):
        parts.append(node_type.upper())
    elif isinstance(node, BinaryOp):
        op = getattr(node, "op", "OP")
        parts.append(f"BOP({op})")
    elif isinstance(node, UnaryOp):
        op = getattr(node, "op", "UOP")
        parts.append(f"UOP({op})")

    # Leaf replacements — strip names/values
    elif isinstance(node, Name):
        parts.append(_VAR)
        return  # leaf — no children
    elif isinstance(node, String):
        parts.append(_STR)
        return
    elif isinstance(node, Number):
        parts.append(_NUM)
        return
    elif isinstance(node, (TrueExpr, FalseExpr)):
        parts.append("BOOL")
        return
    elif isinstance(node, NilExpr):
        parts.append("NIL")
        return

    # Recurse into children
    if isinstance(node, Node):
        for attr in node.__dict__:
            if attr.startswith("_"):
                continue
            child = getattr(node, attr)
            _flatten_child(child, parts)
    elif isinstance(node, list):
        for item in node:
            _flatten(item, parts)


def _flatten_child(child, parts: list[str]) -> None:
    from luaparser.astnodes import Node
    if isinstance(child, Node):
        _flatten(child, parts)
    elif isinstance(child, list):
        for item in child:
            _flatten(item, parts)
```

- [ ] **Step 4.4: Run tests to confirm PASS**

```bash
python -m pytest tests/test_ast_normalizer.py -v
```

- [ ] **Step 4.5: Add `detect_semantic_duplicates()` to `ttt/analyzer/duplicates.py`**

At the end of `ttt/analyzer/duplicates.py`, append:

```python
# ── AST-backed semantic duplicate detection ────────────────────────────────


@dataclass
class SemanticDuplicate:
    """Two functions that are structurally identical despite different variable names."""
    file_a: str
    file_b: str
    similarity: float


def detect_semantic_duplicates(
    lua_files: List[str],
    threshold: float = 0.90,
) -> List[SemanticDuplicate]:
    """Compare all pairs of Lua files for structural similarity.

    Uses AST normalization — catches copy-paste duplicates even when variable
    names were changed. Returns pairs above ``threshold`` similarity.

    Falls back to empty list if ``luaparser`` is unavailable.
    """
    try:
        from ttt.converters.ast_normalizer import normalize_ast_structure, structural_similarity
    except ImportError:
        return []

    results = []
    codes = {}
    for path in lua_files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                codes[path] = f.read()
        except OSError:
            continue

    paths = list(codes.keys())
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            score = structural_similarity(codes[paths[i]], codes[paths[j]])
            if score >= threshold:
                results.append(SemanticDuplicate(
                    file_a=paths[i],
                    file_b=paths[j],
                    similarity=score,
                ))

    return sorted(results, key=lambda x: -x.similarity)
```

Also add the necessary imports at the top of `duplicates.py` if not already there:

```python
from dataclasses import dataclass  # already present
from typing import List            # already present
```

- [ ] **Step 4.6: Write test for `detect_semantic_duplicates`**

```python
# Add to tests/test_ast_normalizer.py:
import os, tempfile
from ttt.analyzer.duplicates import detect_semantic_duplicates, SemanticDuplicate

SWORD_SCRIPT = """
function onUseSword(player, item, fromPos, target, toPos)
    local level = getPlayerLevel(player)
    if level < 50 then
        doPlayerSendTextMessage(player, 22, "Too low level")
        return false
    end
    return true
end
"""

SHIELD_SCRIPT = """
function onUseShield(cid, item, fromPos, target, toPos)
    local lvl = getPlayerLevel(cid)
    if lvl < 50 then
        doPlayerSendTextMessage(cid, 22, "Too low level")
        return false
    end
    return true
end
"""

LOGIN_SCRIPT = """
function onLogin(player)
    player:sendTextMessage(MESSAGE_INFO_DESCR, "Welcome!")
    return true
end
"""


def test_detect_semantic_duplicates_finds_similar_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = os.path.join(tmpdir, "sword.lua")
        p2 = os.path.join(tmpdir, "shield.lua")
        p3 = os.path.join(tmpdir, "login.lua")
        for path, content in [(p1, SWORD_SCRIPT), (p2, SHIELD_SCRIPT), (p3, LOGIN_SCRIPT)]:
            with open(path, "w") as f:
                f.write(content)

        results = detect_semantic_duplicates([p1, p2, p3], threshold=0.80)

        file_pairs = {(os.path.basename(r.file_a), os.path.basename(r.file_b)) for r in results}
        assert ("sword.lua", "shield.lua") in file_pairs


def test_no_duplicates_when_all_different():
    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = os.path.join(tmpdir, "a.lua")
        p2 = os.path.join(tmpdir, "b.lua")
        with open(p1, "w") as f:
            f.write(SWORD_SCRIPT)
        with open(p2, "w") as f:
            f.write(LOGIN_SCRIPT)

        results = detect_semantic_duplicates([p1, p2], threshold=0.90)
        assert results == []
```

- [ ] **Step 4.7: Run all normalizer tests**

```bash
python -m pytest tests/test_ast_normalizer.py -v
```

- [ ] **Step 4.8: Commit**

```bash
git add ttt/converters/ast_normalizer.py ttt/analyzer/duplicates.py tests/test_ast_normalizer.py
git commit -m "feat: add AST structural normalization and semantic duplicate detection"
```

---

## Chunk 3: Wire AST Backend into AnalyzeEngine

### Task 5: Optional AST Backend in AnalyzeEngine

**Context:**
`AnalyzeEngine` in `ttt/analyzer/engine.py` runs each module sequentially (all regex-based). This task adds an optional `use_ast=True` flag that swaps in the AST-backed modules for complexity and dead code analysis, and adds semantic duplicates as a new report section. The flag degrades gracefully: if `luaparser` is unavailable, it silently falls back to the regex modules.

**Files:**

- Modify: `ttt/analyzer/engine.py` — add `use_ast` param, AST module dispatch
- Modify: `ttt/analyzer/engine.py` — extend `AnalysisReport` with `semantic_duplicates`
- Modify: `ttt/analyzer/engine.py` — extend `format_analysis_text()` and `format_analysis_html()` with semantic duplicate section
- Test: `tests/test_ast_engine_integration.py`

---

- [ ] **Step 5.1: Write the failing integration test**

```python
# tests/test_ast_engine_integration.py
import os, tempfile, pytest
from ttt.analyzer.engine import AnalyzeEngine, format_analysis_text

SWORD_LUA = """
function onUseSword(player, item, fromPos, target, toPos)
    local level = getPlayerLevel(player)
    if level < 50 then
        doPlayerSendTextMessage(player, 22, "Too low level")
        return false
    end
    return true
end
"""

SHIELD_LUA = """
function onUseShield(cid, item, fromPos, target, toPos)
    local lvl = getPlayerLevel(cid)
    if lvl < 50 then
        doPlayerSendTextMessage(cid, 22, "Too low level")
        return false
    end
    return true
end
"""


@pytest.fixture
def lua_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        for name, content in [("sword.lua", SWORD_LUA), ("shield.lua", SHIELD_LUA)]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write(content)
        yield tmpdir


def test_engine_runs_with_use_ast(lua_dir):
    engine = AnalyzeEngine(use_ast=True)
    report = engine.analyze(lua_dir)
    assert report is not None


def test_ast_report_has_semantic_duplicates(lua_dir):
    engine = AnalyzeEngine(use_ast=True)
    report = engine.analyze(lua_dir)
    # semantic_duplicates is a new field
    assert hasattr(report, "semantic_duplicates")
    assert len(report.semantic_duplicates) >= 1


def test_ast_report_text_includes_semantic_section(lua_dir):
    engine = AnalyzeEngine(use_ast=True)
    report = engine.analyze(lua_dir)
    text = format_analysis_text(report)
    assert "semantic" in text.lower() or "duplicate" in text.lower()


def test_engine_without_ast_still_works(lua_dir):
    engine = AnalyzeEngine(use_ast=False)
    report = engine.analyze(lua_dir)
    assert report is not None
    assert report.semantic_duplicates == []
```

- [ ] **Step 5.2: Run to confirm FAIL**

```bash
python -m pytest tests/test_ast_engine_integration.py -v 2>&1 | head -20
```

- [ ] **Step 5.3: Extend `AnalysisReport` in `ttt/analyzer/engine.py`**

Find the `AnalysisReport` dataclass and add the new field. Also add the import at the top:

```python
from ttt.analyzer.duplicates import SemanticDuplicate
```

In the dataclass:

```python
@dataclass
class AnalysisReport:
    # ... existing fields ...
    semantic_duplicates: List["SemanticDuplicate"] = field(default_factory=list)
```

- [ ] **Step 5.4: Add `use_ast` to `AnalyzeEngine.__init__` and `analyze()`**

```python
class AnalyzeEngine:
    def __init__(self, enabled_modules=None, use_ast: bool = False):
        self.enabled_modules = enabled_modules or [
            "stats", "dead_code", "duplicates", "storage", "item_usage", "complexity"
        ]
        self.use_ast = use_ast

    def analyze(self, directory: str) -> AnalysisReport:
        report = AnalysisReport()

        # ... existing module dispatch (unchanged) ...

        # AST backend additions
        if self.use_ast:
            report.semantic_duplicates = self._run_semantic_duplicates(directory)
            if "complexity" in self.enabled_modules:
                # Augment existing complexity report with AST data
                # (AST results are richer; regex report remains for fallback)
                pass  # complexity.py AST metrics are accessed via ast_enricher per file

        return report

    def _run_semantic_duplicates(self, directory: str):
        import glob as _glob
        from ttt.analyzer.duplicates import detect_semantic_duplicates
        lua_files = _glob.glob(os.path.join(directory, "**", "*.lua"), recursive=True)
        if not lua_files:
            return []
        return detect_semantic_duplicates(lua_files, threshold=0.85)
```

- [ ] **Step 5.5: Extend `format_analysis_text()` with semantic duplicate section**

In `format_analysis_text()`, add after the duplicates section:

```python
if report.semantic_duplicates:
    lines = []
    lines.append(f"\n{C.YELLOW}Semantic Duplicates (AST-backed){C.RESET}")
    lines.append(f"  {len(report.semantic_duplicates)} structurally identical file pair(s) found:")
    for sd in report.semantic_duplicates[:10]:
        a = os.path.basename(sd.file_a)
        b = os.path.basename(sd.file_b)
        lines.append(f"  {C.DIM}· {a} ↔ {b}  ({sd.similarity:.0%} similar){C.RESET}")
    output.append("\n".join(lines))
```

- [ ] **Step 5.6: Run integration tests**

```bash
python -m pytest tests/test_ast_engine_integration.py -v
```

- [ ] **Step 5.7: Run full test suite to confirm no regressions**

```bash
python -m pytest tests/ -v --tb=short 2>&1 | tail -30
```

Expected: all existing tests pass; new tests pass.

- [ ] **Step 5.8: Commit**

```bash
git add ttt/analyzer/engine.py tests/test_ast_engine_integration.py
git commit -m "feat: add use_ast flag to AnalyzeEngine with semantic duplicate section"
```

---

## Chunk 4: CLI Wiring + Final Polish

### Task 6: Expose `--use-ast` via CLI + Wire `enrich_analysis` into Dry-Run

**Context:**
The `analyze` subcommand in `ttt/main.py` calls `AnalyzeEngine` but has no `use_ast` option. The dry-run flow that generates `oop_guidelines.md` calls `LuaOopAnalyzer` but doesn't call `enrich_analysis`. This task connects both.

**Files:**

- Modify: `ttt/main.py` — add `--use-ast` flag to `analyze` subcommand
- Modify: `ttt/main.py` — call `enrich_analysis` in the dry-run OOP guidelines path
- Test: manual smoke test (CLI is hard to unit-test; we verify via integration test)

---

- [ ] **Step 6.1: Locate the `analyze` subcommand handler in `ttt/main.py`**

```bash
grep -n "analyze\|AnalyzeEngine\|add_parser\|use_ast" ttt/main.py | head -30
```

- [ ] **Step 6.2: Add `--use-ast` argument**

Find the `analyze` subparser argument definitions and add:

```python
analyze_parser.add_argument(
    "--use-ast",
    action="store_true",
    default=False,
    help="Use AST-backed analysis for higher accuracy (requires luaparser).",
)
```

- [ ] **Step 6.3: Pass `use_ast` to `AnalyzeEngine`**

Find where `AnalyzeEngine` is instantiated in the `analyze` handler and change:

```python
engine = AnalyzeEngine(enabled_modules=modules, use_ast=args.use_ast)
```

- [ ] **Step 6.4: Locate the dry-run OOP guidelines generation code**

```bash
grep -n "GuidelinesGenerator\|enrich_analysis\|LuaOopAnalyzer\|oop_guidelines\|dry.run" ttt/main.py | head -20
```

- [ ] **Step 6.5: Add `enrich_analysis` call in the dry-run path**

After the `analyzer.analyze_content(code, rel_path)` call, add:

```python
from ttt.analyzers.ast_enricher import enrich_analysis as _enrich
_enrich(analysis, code)
```

Make sure to import at the top of the function or module, not inline, to avoid repeated imports.

- [ ] **Step 6.6: Smoke test the CLI**

```bash
# Analyze with AST backend
python run.py --help 2>&1 | grep -A5 analyze || true

# If test fixtures are available:
python -m pytest tests/ -v --tb=short -q 2>&1 | tail -20
```

- [ ] **Step 6.7: Commit**

```bash
git add ttt/main.py
git commit -m "feat: expose --use-ast flag in CLI and enrich dry-run guidelines with AST data"
```

---

## Final: Full Test Suite

- [ ] **Step 7.1: Run complete test suite**

```bash
python -m pytest tests/ -v 2>&1 | tail -40
```

Expected: all tests pass.

- [ ] **Step 7.2: Lint**

```bash
ruff check ttt/converters/ast_complexity.py ttt/converters/ast_dead_code.py \
           ttt/converters/ast_normalizer.py ttt/analyzers/ast_enricher.py
```

Fix any issues.

- [ ] **Step 7.3: Final commit**

```bash
git add -u
git commit -m "chore: lint fixes and final cleanup for llm-ast-integration"
```
