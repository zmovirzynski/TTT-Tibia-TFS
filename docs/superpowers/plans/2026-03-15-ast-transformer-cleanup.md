# AST Transformer Cleanup Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix structural issues in the AST-based Lua transformer: eliminate code duplication across function visitors, extract shared utilities, replace fragile `__class__` mutation with proper node replacement, and improve scope matching robustness.

**Architecture:** Extract a shared `ast_utils.py` module for utilities used by both `ScopeAnalyzer` and `ASTTransformVisitor`; consolidate the three near-identical function-visitor methods in each class into a single helper; replace the two `node.__class__` mutation hacks with in-place attribute updates that are compatible with luaparser's serializer; and switch scope matching from a fragile visit-order index to name-based lookup.

**Tech Stack:** Python 3.7+, luaparser (optional dep), unittest

---

## Chunk 1: Shared utilities + test scaffold

### Task 1: Create `ast_utils.py` with shared utility functions

**Files:**

- Create: `ttt/converters/ast_utils.py`
- Create: `tests/test_ast_transformer.py`

These two functions are copy-pasted between `ScopeAnalyzer` and `ASTTransformVisitor`. Extracting them is the first step before touching either class.

- [ ] **Step 1: Write failing tests for the utilities**

Create `tests/test_ast_transformer.py`:

```python
"""Tests for AST-based Lua transformer components."""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from luaparser.astnodes import Name, Index, String, Call
    from ttt.converters.ast_utils import get_function_name, get_base_name, get_wrapper_class
    LUAPARSER_AVAILABLE = True
except ImportError:
    LUAPARSER_AVAILABLE = False


@unittest.skipUnless(LUAPARSER_AVAILABLE, "luaparser not installed")
class TestAstUtils(unittest.TestCase):

    def test_get_function_name_simple(self):
        node = Name("doPlayerAddItem")
        self.assertEqual(get_function_name(node), "doPlayerAddItem")

    def test_get_function_name_index(self):
        # Represents Game["createItem"]
        node = Index(value=Name("Game"), idx=String(b"createItem", "createItem"))
        self.assertEqual(get_function_name(node), "Game.createItem")

    def test_get_function_name_none_for_complex(self):
        # Call node as func — can't extract name
        node = Call(func=Name("f"), args=[])
        self.assertIsNone(get_function_name(node))

    def test_get_base_name_simple(self):
        self.assertEqual(get_base_name(Name("foo")), "foo")

    def test_get_base_name_nested_index(self):
        inner = Index(value=Name("a"), idx=String(b"b", "b"))
        self.assertEqual(get_base_name(inner), "a")

    def test_get_base_name_none(self):
        self.assertIsNone(get_base_name(String(b"x", "x")))

    def test_get_wrapper_class_known(self):
        self.assertEqual(get_wrapper_class("player"), "Player")
        self.assertEqual(get_wrapper_class("creature"), "Creature")
        self.assertEqual(get_wrapper_class("monster"), "Monster")
        self.assertEqual(get_wrapper_class("npc"), "Npc")
        self.assertEqual(get_wrapper_class("item"), "Item")
        self.assertEqual(get_wrapper_class("tile"), "Tile")
        self.assertEqual(get_wrapper_class("position"), "Position")

    def test_get_wrapper_class_fallback(self):
        self.assertEqual(get_wrapper_class("unknown_type"), "Creature")

    def test_get_wrapper_class_none(self):
        # var_type=None should not crash; returns fallback
        self.assertEqual(get_wrapper_class(None), "Creature")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /var/home/gaamelu/development/tools/script-converter
python -m pytest tests/test_ast_transformer.py::TestAstUtils -v
```

Expected: FAIL with `ImportError: cannot import name 'get_function_name' from 'ttt.converters.ast_utils'`

- [ ] **Step 3: Create `ttt/converters/ast_utils.py`**

```python
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
            return f"{base}.{func.idx.s}"
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
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
python -m pytest tests/test_ast_transformer.py::TestAstUtils -v
```

Expected: All 10 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ttt/converters/ast_utils.py tests/test_ast_transformer.py
git commit -m "feat: add ast_utils module with shared AST utility functions"
```

---

## Chunk 2: Wire `ast_utils` into existing classes

### Task 2: Replace duplicate implementations in `ScopeAnalyzer`

**Files:**

- Modify: `ttt/converters/scope_analyzer.py`

The `_get_function_name`, `_get_base_name`, and `get_wrapper_class` at the bottom of `scope_analyzer.py` are duplicates of what's now in `ast_utils`.

> **Context note:** `scope_analyzer.py` has both:
>
> - Instance methods `_get_function_name` / `_get_base_name` on `ScopeAnalyzer` (lines 481–513)
> - Module-level functions `get_wrapper_class` / `get_base_name` / etc. at the bottom (lines 999–1019)

- [ ] **Step 1: Write regression tests to lock in current ScopeAnalyzer behavior before touching it**

Add to `tests/test_ast_transformer.py`:

```python
@unittest.skipUnless(LUAPARSER_AVAILABLE, "luaparser not installed")
class TestScopeAnalyzer(unittest.TestCase):

    def _analyze(self, code: str):
        from luaparser import ast as luaast
        from ttt.converters.scope_analyzer import ScopeAnalyzer
        from ttt.mappings.signatures import SIGNATURE_MAP
        tree = luaast.parse(code)
        analyzer = ScopeAnalyzer(SIGNATURE_MAP)
        return analyzer.analyze(tree)

    def test_param_type_player_from_signature(self):
        code = "function onLogin(cid)\n    return true\nend"
        info = self._analyze(code)
        # cid in onLogin should be typed as 'player'
        scopes = dict(info.function_scopes)
        self.assertIn("onLogin", scopes)
        var = scopes["onLogin"].lookup("cid")
        self.assertIsNotNone(var)
        self.assertEqual(var.var_type, "player")

    def test_local_var_type_from_function_call(self):
        code = (
            "function onLogin(cid)\n"
            "    local target = getCreatureByName('Foo')\n"
            "    return true\nend"
        )
        info = self._analyze(code)
        scopes = dict(info.function_scopes)
        var = scopes["onLogin"].lookup("target")
        self.assertIsNotNone(var)
        self.assertEqual(var.var_type, "creature")

    def test_is_param_flag(self):
        code = "function onLogin(cid)\n    return true\nend"
        info = self._analyze(code)
        scopes = dict(info.function_scopes)
        var = scopes["onLogin"].lookup("cid")
        self.assertTrue(var.is_param)

    def test_local_var_is_not_param(self):
        code = (
            "function onLogin(cid)\n"
            "    local x = 1\n"
            "    return true\nend"
        )
        info = self._analyze(code)
        scopes = dict(info.function_scopes)
        var = scopes["onLogin"].lookup("x")
        self.assertIsNotNone(var)
        self.assertFalse(var.is_param)
```

- [ ] **Step 2: Run the new tests to confirm they pass (no changes yet)**

```bash
python -m pytest tests/test_ast_transformer.py::TestScopeAnalyzer -v
```

Expected: All 4 tests PASS (since we haven't changed anything yet).

- [ ] **Step 3: Replace instance methods with imports from `ast_utils`**

In `ttt/converters/scope_analyzer.py`, add to the existing imports at the top:

```python
from .ast_utils import get_function_name, get_base_name, get_wrapper_class
```

Then delete the two instance methods `_get_function_name` (lines ~481–498) and `_get_base_name` (lines ~500–513) from the `ScopeAnalyzer` class.

Change every call in the class body:

- `self._get_function_name(x)` → `get_function_name(x)`
- `self._get_base_name(x)` → `get_base_name(x)`

Also delete the module-level `get_wrapper_class` function at the bottom of the file (lines ~999–1019) since `ast_utils.get_wrapper_class` is now canonical. Update its callers (the module-level helpers `is_creature_variable`, etc. don't use it; verify with grep).

- [ ] **Step 4: Run tests to verify no regressions**

```bash
python -m pytest tests/test_ast_transformer.py tests/test_ttt.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ttt/converters/scope_analyzer.py tests/test_ast_transformer.py
git commit -m "refactor: use shared ast_utils in ScopeAnalyzer, remove duplicate helpers"
```

---

### Task 3: Replace duplicate implementations in `ASTTransformVisitor`

**Files:**

- Modify: `ttt/converters/ast_transform_visitor.py`

Same cleanup for `ASTTransformVisitor._get_function_name`, `._get_base_name`, and `._get_wrapper_class`.

- [ ] **Step 1: Import from `ast_utils` and delete local implementations**

Add to imports in `ast_transform_visitor.py`:

```python
from .ast_utils import get_function_name, get_base_name, get_wrapper_class
```

Delete instance methods:

- `_get_function_name` (~lines 173–190)
- `_get_base_name` (~lines 192–205)
- `_get_wrapper_class` (~lines 103–121)

Update every call in the class body:

- `self._get_function_name(x)` → `get_function_name(x)`
- `self._get_base_name(x)` → `get_base_name(x)`
- `self._get_wrapper_class(x)` → `get_wrapper_class(x)`

- [ ] **Step 2: Run tests**

```bash
python -m pytest tests/test_ast_transformer.py tests/test_ttt.py -v
```

Expected: All tests PASS.

- [ ] **Step 3: Commit**

```bash
git add ttt/converters/ast_transform_visitor.py
git commit -m "refactor: use shared ast_utils in ASTTransformVisitor, remove duplicate helpers"
```

---

## Chunk 3: Eliminate function-visitor duplication

### Task 4: Deduplicate `visit_Function` / `visit_LocalFunction` / `visit_AnonymousFunction` in `ScopeAnalyzer`

**Files:**

- Modify: `ttt/converters/scope_analyzer.py`

The three visitor methods (`visit_Function`, `visit_LocalFunction`, `visit_AnonymousFunction`) share ~50 lines of identical logic each. Extract to `_enter_function_scope(func_name, params)`.

- [ ] **Step 1: Add a test that exercises all three function forms**

Add to `tests/test_ast_transformer.py` in `TestScopeAnalyzer`:

```python
def test_anonymous_function_param_typed(self):
    """onUse = function(cid, item, ...) end — anonymous function via assignment."""
    code = (
        "onUse = function(cid, item, frompos, item2, topos)\n"
        "    return true\nend"
    )
    info = self._analyze(code)
    # The anonymous function should be associated with 'onUse'
    names = [name for name, _ in info.function_scopes]
    self.assertIn("onUse", names)
    scope = dict(info.function_scopes)["onUse"]
    var = scope.lookup("cid")
    self.assertIsNotNone(var)
    self.assertEqual(var.var_type, "player")

def test_local_function_param_typed(self):
    """local function handler(cid) end — local function declaration."""
    code = "local function onLogin(cid)\n    return true\nend"
    info = self._analyze(code)
    names = [name for name, _ in info.function_scopes]
    self.assertIn("onLogin", names)
    scope = dict(info.function_scopes)["onLogin"]
    var = scope.lookup("cid")
    self.assertIsNotNone(var)
    self.assertEqual(var.var_type, "player")
```

- [ ] **Step 2: Run these new tests to confirm they pass before refactoring**

```bash
python -m pytest tests/test_ast_transformer.py::TestScopeAnalyzer -v
```

Expected: All tests PASS.

- [ ] **Step 3: Extract `_enter_function_scope` helper in `ScopeAnalyzer`**

Add this private method to the `ScopeAnalyzer` class:

```python
def _enter_function_scope(self, func_name: str, params) -> Scope:
    """Push a new scope for a function and register its parameters.

    Args:
        func_name: The function name (or '<anonymous>').
        params: The parameter nodes list (luaparser Name nodes).

    Returns:
        The newly created Scope.
    """
    new_scope = self._push_scope()

    if self.scope_info:
        self.scope_info.function_scopes.append((func_name, new_scope))

    if params:
        for idx, param in enumerate(params):
            if isinstance(param, Name):
                param_name = param.id
                var_type = self._infer_param_type(func_name, idx, param_name)
                if var_type is None:
                    var_type = "creature"
                renamed = self._get_renamed_name(param_name, var_type)
                info = VariableInfo(
                    name=param_name,
                    var_type=var_type,
                    is_param=True,
                    renamed_name=renamed,
                    scope_level=new_scope.level,
                )
                new_scope.define(param_name, info)
                self._record_variable(info)

    return new_scope
```

Then replace the bodies of all three visitor methods:

```python
def visit_Function(self, node: Function) -> None:
    func_name = "<anonymous>"
    if hasattr(node, "name") and node.name:
        if isinstance(node.name, Name):
            func_name = node.name.id
        elif isinstance(node.name, str):
            func_name = node.name
    elif self._current_function_name:
        func_name = self._current_function_name
        self._current_function_name = None
    self._enter_function_scope(func_name, getattr(node, "args", None) or [])

def visit_LocalFunction(self, node) -> None:
    func_name = "<anonymous>"
    if hasattr(node, "name") and node.name:
        if isinstance(node.name, Name):
            func_name = node.name.id
        elif isinstance(node.name, str):
            func_name = node.name
    elif self._current_function_name:
        func_name = self._current_function_name
        self._current_function_name = None
    self._enter_function_scope(func_name, getattr(node, "args", None) or [])

def visit_AnonymousFunction(self, node: AnonymousFunction) -> None:
    func_name = "<anonymous>"
    if self._current_function_name:
        func_name = self._current_function_name
        self._current_function_name = None
    self._enter_function_scope(func_name, getattr(node, "args", None) or [])
```

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/test_ast_transformer.py tests/test_ttt.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ttt/converters/scope_analyzer.py tests/test_ast_transformer.py
git commit -m "refactor: extract _enter_function_scope in ScopeAnalyzer to remove visitor duplication"
```

---

### Task 5: Deduplicate function visitors in `ASTTransformVisitor`

**Files:**

- Modify: `ttt/converters/ast_transform_visitor.py`

Same pattern — the three function visitors are nearly identical (signature update + scope tracking).

- [ ] **Step 1: Add AST transformer tests for function forms**

Add to `tests/test_ast_transformer.py`:

```python
@unittest.skipUnless(LUAPARSER_AVAILABLE, "luaparser not installed")
class TestASTTransformVisitor(unittest.TestCase):

    def _transform(self, code: str) -> str:
        from luaparser import ast as luaast
        from ttt.converters.ast_lua_transformer import ASTLuaTransformer
        from ttt.mappings.tfs03_functions import TFS03_TO_1X
        t = ASTLuaTransformer(TFS03_TO_1X, "tfs03")
        return t.transform(code, "test.lua")

    def test_signature_named_function(self):
        code = "function onLogin(cid)\n    return true\nend"
        result = self._transform(code)
        self.assertIn("onLogin(player)", result)
        self.assertNotIn("onLogin(cid)", result)

    def test_signature_anonymous_function_assignment(self):
        code = "onLogin = function(cid)\n    return true\nend"
        result = self._transform(code)
        self.assertIn("player", result)
        self.assertNotIn("(cid)", result)

    def test_signature_local_function(self):
        code = "local function onLogin(cid)\n    return true\nend"
        result = self._transform(code)
        self.assertIn("player", result)
        self.assertNotIn("(cid)", result)

    def test_method_call_converted(self):
        code = (
            "function onLogin(cid)\n"
            "    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, 'hi')\n"
            "    return true\nend"
        )
        result = self._transform(code)
        self.assertIn("sendTextMessage", result)
        self.assertNotIn("doPlayerSendTextMessage", result)
```

- [ ] **Step 2: Run to verify they pass before refactoring**

```bash
python -m pytest tests/test_ast_transformer.py::TestASTTransformVisitor -v
```

Expected: All 4 tests PASS.

- [ ] **Step 3: Extract `_enter_function_scope` helper in `ASTTransformVisitor`**

Add to the class:

```python
def _enter_function_scope(self, func_name: str, params) -> None:
    """Set up scope tracking and apply signature transformation for a function.

    Args:
        func_name: The function name (or '<anonymous>').
        params: The mutable parameter node list from the function AST node.
    """
    self.current_function_name = func_name

    if self._function_scope_index < len(self.scope_info.function_scopes):
        _, self.current_function_scope = self.scope_info.function_scopes[self._function_scope_index]
        self._function_scope_index += 1
    else:
        self.current_function_scope = Scope(
            parent=self.scope_info.global_scope, level=1
        )

    self.scope_stack.append(self.current_function_scope)

    if func_name in SIGNATURE_MAP and params is not None:
        old_sig, new_sig = SIGNATURE_MAP[func_name]
        old_params = old_sig.get("params", [])
        new_params = new_sig.get("params", [])

        for i, param in enumerate(params):
            if isinstance(param, Name) and i < len(old_params):
                old_name = old_params[i]
                if i < len(new_params):
                    new_name = new_params[i]
                    if old_name != new_name:
                        self.param_renames[old_name] = new_name
                        param.id = new_name
                        self.stats["signatures_updated"] += 1

        current_count = len(params)
        for i in range(current_count, len(new_params)):
            params.append(Name(new_params[i]))
            self.stats["signatures_updated"] += 1

def _exit_function_scope(self) -> None:
    """Tear down scope tracking after visiting a function's body."""
    if self.scope_stack:
        self.scope_stack.pop()
    self.current_function_scope = self.scope_stack[-1] if self.scope_stack else None
    self.param_renames = {}
```

Replace the three visitor method bodies:

```python
def visit_Function(self, node: Function) -> None:
    func_name = "<anonymous>"
    if hasattr(node, "name") and node.name:
        if isinstance(node.name, Name):
            func_name = node.name.id
        elif isinstance(node.name, str):
            func_name = node.name
    elif hasattr(self, "_current_function_name") and self._current_function_name:
        func_name = self._current_function_name
        self._current_function_name = None
    params = node.args if hasattr(node, "args") and node.args is not None else []
    self._enter_function_scope(func_name, params)
    self.generic_visit(node)
    self._exit_function_scope()

def visit_LocalFunction(self, node) -> None:
    func_name = "<anonymous>"
    if hasattr(node, "name") and node.name:
        if isinstance(node.name, Name):
            func_name = node.name.id
        elif isinstance(node.name, str):
            func_name = node.name
    elif hasattr(self, "_current_function_name") and self._current_function_name:
        func_name = self._current_function_name
        self._current_function_name = None
    params = node.args if hasattr(node, "args") and node.args is not None else []
    self._enter_function_scope(func_name, params)
    self.generic_visit(node)
    self._exit_function_scope()

def visit_AnonymousFunction(self, node: AnonymousFunction) -> None:
    func_name = "<anonymous>"
    if hasattr(self, "_current_function_name") and self._current_function_name:
        func_name = self._current_function_name
        self._current_function_name = None
    params = node.args if hasattr(node, "args") and node.args is not None else []
    self._enter_function_scope(func_name, params)
    self.generic_visit(node)
    self._exit_function_scope()
```

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/test_ast_transformer.py tests/test_ttt.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ttt/converters/ast_transform_visitor.py tests/test_ast_transformer.py
git commit -m "refactor: extract _enter/_exit_function_scope in ASTTransformVisitor to remove visitor duplication"
```

---

## Chunk 4: Fix scope matching + `__class__` mutation

### Task 6: Replace index-based scope matching with name-based lookup

**Files:**

- Modify: `ttt/converters/ast_transform_visitor.py`

`_function_scope_index` relies on `ScopeAnalyzer` and `ASTTransformVisitor` visiting the AST in identical order. When these diverge (e.g., because one uses `visit_Chunk` pre-processing and the other doesn't), scopes get matched to the wrong functions. Name-based lookup is much more robust.

> **Context note on the approach:** `ScopeInfo.function_scopes` is a list of `(name, Scope)` tuples that may contain duplicates (multiple anonymous functions, multiple same-named helpers). The fix: find the first scope whose name matches AND whose parameters align with what the visitor is currently processing. Fall back to `_function_scope_index` as a secondary strategy only if name lookup fails.

- [ ] **Step 1: Add a test that verifies correct scope matching for two same-level functions**

Add to `tests/test_ast_transformer.py` in `TestASTTransformVisitor`:

```python
def test_two_functions_independent_scopes(self):
    """Two functions in the same file should each get correct param transformations."""
    code = (
        "function onLogin(cid)\n"
        "    return true\nend\n"
        "function onLogout(cid)\n"
        "    return true\nend"
    )
    result = self._transform(code)
    # Both should have 'player' param, neither should have 'cid' left
    self.assertEqual(result.count("(player)"), 2)
    self.assertNotIn("(cid)", result)
```

- [ ] **Step 2: Run to confirm current behavior (may already pass or expose the bug)**

```bash
python -m pytest tests/test_ast_transformer.py::TestASTTransformVisitor::test_two_functions_independent_scopes -v
```

Note actual result. If it fails, the index bug is confirmed.

- [ ] **Step 3: Add name-based scope lookup to `_enter_function_scope`**

Replace the `_function_scope_index` block inside `_enter_function_scope`:

```python
# Try to find the scope by name first (robust against traversal-order differences)
matched_scope = self._find_scope_for_function(func_name)
if matched_scope is not None:
    self.current_function_scope = matched_scope
else:
    # Fall back to sequential index (handles anonymous functions with no name)
    if self._function_scope_index < len(self.scope_info.function_scopes):
        _, self.current_function_scope = self.scope_info.function_scopes[
            self._function_scope_index
        ]
        self._function_scope_index += 1
    else:
        self.current_function_scope = Scope(
            parent=self.scope_info.global_scope, level=1
        )
```

Add the lookup helper to the class:

```python
def _find_scope_for_function(self, func_name: str):
    """Find the scope entry matching func_name, skipping already-consumed entries.

    Uses a per-name counter so that two functions with the same name get
    different scopes in the order they were visited during analysis.

    Args:
        func_name: The function name to look up.

    Returns:
        The matching Scope, or None if not found.
    """
    if func_name == "<anonymous>":
        return None  # Can't disambiguate anonymous functions by name alone

    if not hasattr(self, "_scope_name_counters"):
        self._scope_name_counters = {}

    visit_count = self._scope_name_counters.get(func_name, 0)
    matches = [
        scope
        for name, scope in self.scope_info.function_scopes
        if name == func_name
    ]

    if visit_count < len(matches):
        self._scope_name_counters[func_name] = visit_count + 1
        return matches[visit_count]

    return None
```

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/test_ast_transformer.py tests/test_ttt.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ttt/converters/ast_transform_visitor.py tests/test_ast_transformer.py
git commit -m "fix: replace index-based scope matching with name-based lookup in ASTTransformVisitor"
```

---

### Task 7: Replace `__class__` mutation with safe in-place attribute update

**Files:**

- Modify: `ttt/converters/ast_transform_visitor.py`

Two places mutate `node.__class__`:

1. `_transform_function_call` line ~366: `node.__class__ = Invoke` (converting a Call to a method Invoke)
2. `visit_Table` line ~765: `node.__class__ = Call` (converting a Table to a Position() call)

The fix uses in-place attribute assignment without changing `__class__`. luaparser's `ast.to_lua_source` dispatches on `node.__class__.__name__` for serialization, so we must keep the class change — but we can do it safely by also calling `__init__` equivalents to ensure the object is fully initialized as the new type.

> **Context note:** luaparser AST nodes don't use `__slots__`. Setting `__class__` on a plain object and then assigning the required attributes _does_ work in CPython. The risk is not correctness but surprising `isinstance` results during debugging. The safest improvement given this constraint: keep `__class__` mutation but immediately verify required attributes for the target class are set, and add a comment explaining why.

- [ ] **Step 1: Add tests for the two mutation sites**

Add to `tests/test_ast_transformer.py` in `TestASTTransformVisitor`:

```python
def test_method_call_result_is_invoke_syntax(self):
    """Transformed function calls should produce obj:method() syntax."""
    code = (
        "function onLogin(cid)\n"
        "    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, 'hi')\n"
        "    return true\nend"
    )
    result = self._transform(code)
    # Method invocation syntax uses colon
    self.assertIn(":", result)
    self.assertIn("sendTextMessage", result)

def test_position_table_converted(self):
    """{x=100, y=200, z=7} should become Position(100, 200, 7)."""
    code = "local pos = {x=100, y=200, z=7}"
    result = self._transform(code)
    self.assertIn("Position(", result)
    self.assertNotIn("{x=", result)
```

- [ ] **Step 2: Run tests to confirm current behavior**

```bash
python -m pytest tests/test_ast_transformer.py::TestASTTransformVisitor::test_method_call_result_is_invoke_syntax tests/test_ast_transformer.py::TestASTTransformVisitor::test_position_table_converted -v
```

Expected: Both PASS (mutation currently works). These are regression guards.

- [ ] **Step 3: Annotate both mutation sites with safety comments**

In `_transform_function_call` around the `node.__class__ = Invoke` block:

```python
# --- Node-class mutation: luaparser serializes by __class__.__name__, so we
# must change the class to produce "obj:method()" output.  We also set every
# attribute that Invoke.__init__ would set so the node is fully valid.
# isinstance() checks on this node will return True for Invoke after this.
node.__class__ = Invoke
node.source = obj_node
node.func = Name(method_name)
node.args = new_args
```

In `visit_Table` around the `node.__class__ = Call` block:

```python
# --- Node-class mutation: transform table literal into a constructor call.
# luaparser serializes Call nodes as "func(args)", which gives us Position(x,y,z).
node.__class__ = Call
node.func = Name("Position")
node.args = [x_val, y_val, z_val]
# Clear the 'fields' attribute so the serializer doesn't see stale Table data.
node.fields = []
```

> **Note:** `node.fields = []` on the now-Call node prevents luaparser from accidentally accessing the old Table data if it walks node attributes. This is the primary safety improvement here.

- [ ] **Step 4: Run full test suite**

```bash
python -m pytest tests/test_ast_transformer.py tests/test_ttt.py -v
```

Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add ttt/converters/ast_transform_visitor.py tests/test_ast_transformer.py
git commit -m "fix: annotate __class__ mutation sites and clear stale fields attribute in Table→Call transform"
```

---

## Chunk 5: Final polish + double-import cleanup

### Task 8: Remove redundant import and minor cleanup

**Files:**

- Modify: `ttt/engine.py`
- Modify: `ttt/converters/ast_transform_visitor.py`

- [ ] **Step 1: Remove redundant import inside `_convert_lua_files`**

In `ttt/engine.py`, the `_convert_lua_files` method (~line 402) re-imports `ASTLuaTransformer` even though it was already imported at module level. Delete the inner import:

```python
# DELETE these three lines inside _convert_lua_files:
from .converters.ast_lua_transformer import ASTLuaTransformer
```

The module-level `ASTLuaTransformer` (already guarded by `AST_AVAILABLE`) is sufficient.

- [ ] **Step 2: Remove unused `Statement` type hint in `ASTTransformVisitor.__init__`**

Line 76: `self.defensive_checks: List[Statement] = []` — `Statement` is not imported anywhere. Change to:

```python
self.defensive_checks: List = []
```

- [ ] **Step 3: Run full test suite**

```bash
python -m pytest tests/test_ast_transformer.py tests/test_ttt.py -v
```

Expected: All tests PASS.

- [ ] **Step 4: Run linter**

```bash
ruff check ttt/ tests/
```

Fix any issues reported.

- [ ] **Step 5: Final commit**

```bash
git add ttt/engine.py ttt/converters/ast_transform_visitor.py
git commit -m "fix: remove redundant ASTLuaTransformer import in engine.py and fix type hint"
```

---

## Summary

| Task | Files Changed                                         | What It Fixes                                      |
| ---- | ----------------------------------------------------- | -------------------------------------------------- |
| 1    | `ast_utils.py` (new), `test_ast_transformer.py` (new) | Shared utility foundation                          |
| 2    | `scope_analyzer.py`                                   | Removes 2 duplicate instance methods               |
| 3    | `ast_transform_visitor.py`                            | Removes 3 duplicate instance methods               |
| 4    | `scope_analyzer.py`                                   | Deduplicates 3 function visitors (~150 lines → 30) |
| 5    | `ast_transform_visitor.py`                            | Deduplicates 3 function visitors (~150 lines → 30) |
| 6    | `ast_transform_visitor.py`                            | Fixes fragile index-based scope matching           |
| 7    | `ast_transform_visitor.py`                            | Makes `__class__` mutations explicit and safe      |
| 8    | `engine.py`, `ast_transform_visitor.py`               | Removes dead code                                  |
