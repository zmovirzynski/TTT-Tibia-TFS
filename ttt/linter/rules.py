"""
Lint rules for TFS/OTServ Lua scripts.

Each rule is a class that inherits from LintRule and implements check().
Rules return a list of LintIssue objects.
"""

import re
from enum import Enum
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class LintSeverity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"
    HINT = "HINT"


@dataclass
class LintIssue:
    line: int
    column: int
    severity: LintSeverity
    rule_id: str
    message: str
    suggestion: str = ""
    fixable: bool = False

    def __repr__(self):
        sev = self.severity.value
        return f"L{self.line}:{self.column}  {sev:<8s} [{self.rule_id}] {self.message}"


# ---------------------------------------------------------------------------
# Base rule class
# ---------------------------------------------------------------------------

class LintRule:
    """Base class for all lint rules."""

    rule_id: str = ""
    description: str = ""
    severity: LintSeverity = LintSeverity.WARNING

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        """Analyze code and return list of issues found."""
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Rule: deprecated-api
# ---------------------------------------------------------------------------

class DeprecatedApiRule(LintRule):
    """Detects deprecated TFS 0.3/0.4 procedural API calls."""

    rule_id = "deprecated-api"
    description = "Detects deprecated TFS 0.3/0.4 function calls"
    severity = LintSeverity.WARNING

    def __init__(self):
        # Lazy import to avoid circular deps
        from ..mappings.tfs03_functions import TFS03_TO_1X
        from ..mappings.tfs04_functions import TFS04_TO_1X

        # Build a combined set of all deprecated function names
        self._deprecated: Dict[str, str] = {}
        for func_name, info in TFS03_TO_1X.items():
            method = info.get("method", "")
            obj_type = info.get("obj_type", "")
            static_class = info.get("static_class", "")
            if static_class:
                replacement = f"{static_class}.{method}()"
            elif obj_type:
                replacement = f"{obj_type}:{method}()"
            else:
                replacement = f"{method}()"
            self._deprecated[func_name] = replacement

        # Add TFS 0.4 functions not already in 0.3 map
        for func_name, info in TFS04_TO_1X.items():
            if func_name not in self._deprecated:
                method = info.get("method", "")
                obj_type = info.get("obj_type", "")
                static_class = info.get("static_class", "")
                if static_class:
                    replacement = f"{static_class}.{method}()"
                elif obj_type:
                    replacement = f"{obj_type}:{method}()"
                else:
                    replacement = f"{method}()"
                self._deprecated[func_name] = replacement

        # Pre-compile regex for matching function calls
        escaped = [re.escape(f) for f in self._deprecated.keys()]
        self._pattern = re.compile(
            r'\b(' + '|'.join(escaped) + r')\s*\(',
            re.MULTILINE
        )

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            # Skip comments
            if stripped.startswith("--"):
                continue
            for match in self._pattern.finditer(line):
                func_name = match.group(1)
                replacement = self._deprecated[func_name]
                col = match.start() + 1
                issues.append(LintIssue(
                    line=i,
                    column=col,
                    severity=self.severity,
                    rule_id=self.rule_id,
                    message=f"Deprecated API: {func_name}() → {replacement}",
                    suggestion=f"Replace with {replacement}",
                    fixable=True,
                ))
        return issues


# ---------------------------------------------------------------------------
# Rule: unused-parameter
# ---------------------------------------------------------------------------

class UnusedParameterRule(LintRule):
    """Detects function parameters that are declared but never used in the body."""

    rule_id = "unused-parameter"
    description = "Detects function parameters that are never used in the body"
    severity = LintSeverity.INFO

    _func_pattern = re.compile(
        r'function\s+(?:\w+[.:])?(\w+)\s*\(([^)]*)\)',
        re.MULTILINE
    )

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []

        for match in self._func_pattern.finditer(code):
            func_name = match.group(1)
            params_str = match.group(2)
            if not params_str.strip():
                continue

            params = [p.strip() for p in params_str.split(",") if p.strip()]
            func_start = match.end()

            # Find matching 'end' for this function
            func_body = self._extract_function_body(code, func_start)
            if not func_body:
                continue

            # Determine the line number of the function declaration
            func_line = code[:match.start()].count("\n") + 1

            for param in params:
                # Skip common convention names like _ or ...
                if param == "_" or param == "...":
                    continue
                # Check if param is used in the body (as word boundary)
                pattern = re.compile(r'\b' + re.escape(param) + r'\b')
                if not pattern.search(func_body):
                    # Find column of param in the declaration line
                    param_pos = params_str.find(param)
                    col = match.start(2) - self._line_start(code, match.start(2)) + param_pos + 1
                    issues.append(LintIssue(
                        line=func_line,
                        column=col,
                        severity=self.severity,
                        rule_id=self.rule_id,
                        message=f"Parameter '{param}' is declared but never used in '{func_name}'",
                        suggestion=f"Remove unused parameter or use it in the function body",
                    ))

        return issues

    def _line_start(self, code: str, pos: int) -> int:
        """Find start of line containing position."""
        return code.rfind("\n", 0, pos) + 1

    def _extract_function_body(self, code: str, start: int) -> Optional[str]:
        """Extract the body of a function from start to matching 'end'."""
        depth = 1
        i = start
        # Keywords that increase depth
        openers = re.compile(
            r'\b(function|if|for|while|repeat|do)\b'
        )
        closers = re.compile(r'\bend\b')
        until_closer = re.compile(r'\buntil\b')

        in_string = None
        in_long_string = False
        long_string_close = ""

        while i < len(code):
            ch = code[i]

            # Handle long strings/comments [[ ... ]] or [=[ ... ]=]
            if not in_string and not in_long_string:
                if code[i:i+2] == "--":
                    # Comment
                    long_match = re.match(r'--\[(=*)\[', code[i:])
                    if long_match:
                        eq = long_match.group(1)
                        close_tag = f"]{eq}]"
                        end_pos = code.find(close_tag, i + len(long_match.group(0)))
                        if end_pos == -1:
                            return code[start:i]
                        i = end_pos + len(close_tag)
                        continue
                    else:
                        # Single line comment
                        newline = code.find("\n", i)
                        if newline == -1:
                            return code[start:i]
                        i = newline + 1
                        continue

                long_match = re.match(r'\[(=*)\[', code[i:])
                if long_match:
                    eq = long_match.group(1)
                    close_tag = f"]{eq}]"
                    end_pos = code.find(close_tag, i + len(long_match.group(0)))
                    if end_pos == -1:
                        return code[start:i]
                    i = end_pos + len(close_tag)
                    continue

            # Handle strings
            if not in_long_string:
                if ch in ('"', "'"):
                    if not in_string:
                        in_string = ch
                    elif in_string == ch:
                        in_string = None
                    i += 1
                    continue

                if in_string:
                    if ch == "\\" and i + 1 < len(code):
                        i += 2
                        continue
                    i += 1
                    continue

            # Look for keywords (only outside strings)
            rest = code[i:]

            # Check for 'repeat' (paired with 'until' not 'end')
            repeat_m = re.match(r'\brepeat\b', rest)
            if repeat_m:
                depth += 1
                i += repeat_m.end()
                continue

            until_m = re.match(r'\buntil\b', rest)
            if until_m:
                depth -= 1
                if depth == 0:
                    return code[start:i]
                i += until_m.end()
                continue

            open_m = re.match(r'\b(function|if|for|while|do)\b', rest)
            if open_m:
                depth += 1
                i += open_m.end()
                continue

            close_m = re.match(r'\bend\b', rest)
            if close_m:
                depth -= 1
                if depth == 0:
                    return code[start:i]
                i += close_m.end()
                continue

            i += 1

        return code[start:]


# ---------------------------------------------------------------------------
# Rule: missing-return
# ---------------------------------------------------------------------------

class MissingReturnRule(LintRule):
    """Detects TFS callbacks that don't return true/false."""

    rule_id = "missing-return"
    description = "Callbacks should return true or false"
    severity = LintSeverity.WARNING

    # Known callbacks that should return a value
    CALLBACKS = {
        "onUse", "onStepIn", "onStepOut", "onEquip", "onDeEquip",
        "onSay", "onLogin", "onLogout", "onDeath", "onKill",
        "onPrepareDeath", "onHealthChange", "onManaChange",
        "onTextEdit", "onThink", "onModalWindow", "onAddItem",
        "onRemoveItem", "onLook", "onTradeRequest", "onTradeAccept",
        "onCastSpell", "onTargetCreature", "onMoveCreature",
    }

    _func_pattern = re.compile(
        r'function\s+(?:\w+[.:])?(\w+)\s*\([^)]*\)',
        re.MULTILINE
    )

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []

        for match in self._func_pattern.finditer(code):
            func_name = match.group(1)
            if func_name not in self.CALLBACKS:
                continue

            func_start = match.end()
            func_body = self._extract_body_simple(code, func_start)
            if func_body is None:
                continue

            func_line = code[:match.start()].count("\n") + 1

            # Check if there's any return statement in the body
            if not re.search(r'\breturn\b', func_body):
                issues.append(LintIssue(
                    line=func_line,
                    column=1,
                    severity=self.severity,
                    rule_id=self.rule_id,
                    message=f"Callback '{func_name}' should return true or false",
                    suggestion="Add 'return true' at the end of the function",
                    fixable=True,
                ))

        return issues

    def _extract_body_simple(self, code: str, start: int) -> Optional[str]:
        """Quick extraction of function body text."""
        depth = 1
        i = start
        in_string = None

        while i < len(code):
            ch = code[i]

            # Skip comments
            if not in_string and code[i:i+2] == "--":
                nl = code.find("\n", i)
                if nl == -1:
                    break
                i = nl + 1
                continue

            # Handle strings
            if ch in ('"', "'"):
                if not in_string:
                    in_string = ch
                elif in_string == ch:
                    in_string = None
                i += 1
                continue

            if in_string:
                if ch == "\\" and i + 1 < len(code):
                    i += 2
                else:
                    i += 1
                continue

            rest = code[i:]

            # Block openers
            m = re.match(r'\b(function|if|for|while|do|repeat)\b', rest)
            if m:
                depth += 1
                i += m.end()
                continue

            # Block closers
            m = re.match(r'\b(end|until)\b', rest)
            if m:
                depth -= 1
                if depth == 0:
                    return code[start:i]
                i += m.end()
                continue

            i += 1

        return code[start:] if start < len(code) else None


# ---------------------------------------------------------------------------
# Rule: invalid-callback-signature
# ---------------------------------------------------------------------------

class InvalidCallbackSignatureRule(LintRule):
    """Detects callbacks with wrong parameter count for their event type."""

    rule_id = "invalid-callback-signature"
    description = "Callback signature doesn't match expected parameters"
    severity = LintSeverity.WARNING

    def __init__(self):
        from ..mappings.signatures import SIGNATURE_MAP
        self._sig_map = SIGNATURE_MAP

    _func_pattern = re.compile(
        r'function\s+(?:\w+[.:])?(\w+)\s*\(([^)]*)\)',
        re.MULTILINE
    )

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []

        for match in self._func_pattern.finditer(code):
            event_name = match.group(1)
            params_str = match.group(2)

            if event_name not in self._sig_map:
                continue

            old_sig, new_sig = self._sig_map[event_name]
            params = [p.strip() for p in params_str.split(",") if p.strip()]
            expected_new = new_sig["params"]

            # Check against both old and new signatures
            all_valid = [old_sig["params"]] + old_sig.get("alt_params", []) + [expected_new]
            valid_counts = set(len(v) for v in all_valid)

            if len(params) not in valid_counts:
                func_line = code[:match.start()].count("\n") + 1
                expected_str = ", ".join(expected_new)
                issues.append(LintIssue(
                    line=func_line,
                    column=1,
                    severity=self.severity,
                    rule_id=self.rule_id,
                    message=(
                        f"'{event_name}' has {len(params)} parameters, "
                        f"expected: ({expected_str})"
                    ),
                    suggestion=f"Update signature to: function {event_name}({expected_str})",
                    fixable=True,
                ))

        return issues


# ---------------------------------------------------------------------------
# Rule: global-variable-leak
# ---------------------------------------------------------------------------

class GlobalVariableLeakRule(LintRule):
    """Detects assignments to undeclared variables (missing 'local')."""

    rule_id = "global-variable-leak"
    description = "Variable assigned without 'local' keyword (possible global leak)"
    severity = LintSeverity.WARNING

    # Common Lua/TFS globals that are okay
    KNOWN_GLOBALS = {
        # Lua builtins
        "print", "type", "tostring", "tonumber", "pairs", "ipairs",
        "table", "string", "math", "os", "io", "error", "assert",
        "pcall", "xpcall", "require", "dofile", "loadfile", "load",
        "setmetatable", "getmetatable", "rawget", "rawset", "rawequal",
        "select", "unpack", "next", "coroutine", "debug",
        # TFS globals
        "Game", "Player", "Creature", "Item", "Position", "Tile",
        "Monster", "Npc", "Town", "House", "Guild", "Group",
        "Vocation", "Condition", "Combat", "Container", "Spell",
        "Action", "MoveEvent", "TalkAction", "CreatureEvent",
        "GlobalEvent", "Weapon", "Party", "ModalWindow",
        "db", "result", "configManager",
        # Common patterns
        "ITEM_", "CONST_", "MESSAGE_", "TALKTYPE_", "COMBAT_",
        "CONDITION_", "SKULL_", "DIRECTION_", "RETURNVALUE_",
        "FLUID_", "TEXTCOLOR_", "CLIENTOS_",
    }

    # Pattern: "varname = expr" at the start of a line (not preceded by local)
    _assign_pattern = re.compile(
        r'^(\s*)(\w+)\s*=\s*(?!.*[=<>!~])',
        re.MULTILINE
    )

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []

        # Collect all known local declarations
        locals_declared: Set[str] = set()
        # Collect function parameter names
        func_params: Set[str] = set()

        func_pattern = re.compile(r'function\s+(?:\w+[.:])?(\w+)\s*\(([^)]*)\)')
        for m in func_pattern.finditer(code):
            func_name = m.group(1)
            params = [p.strip() for p in m.group(2).split(",") if p.strip()]
            func_params.update(params)
            locals_declared.add(func_name)

        # Find local declarations
        local_pattern = re.compile(r'\blocal\s+(\w+)')
        for m in local_pattern.finditer(code):
            locals_declared.add(m.group(1))

        # Find "for var" declarations
        for_pattern = re.compile(r'\bfor\s+(\w+)')
        for m in for_pattern.finditer(code):
            locals_declared.add(m.group(1))

        for i, line in enumerate(lines, 1):
            stripped = line.strip()

            # Skip empty lines, comments
            if not stripped or stripped.startswith("--"):
                continue

            # Skip lines that start with 'local', 'function', 'return', 'if', 'for', etc.
            if re.match(r'^\s*(local|function|return|if|else|elseif|end|for|while|repeat|until|do|break)\b', line):
                continue

            # Skip method calls (obj:method() or obj.method())
            if re.match(r'^\s*\w+[\.:]\w+', line):
                continue

            m = self._assign_pattern.match(line)
            if m:
                var_name = m.group(2)

                # Skip known globals
                if var_name in self.KNOWN_GLOBALS:
                    continue
                # Skip if it starts with a known prefix
                if any(var_name.startswith(p) for p in
                       ("ITEM_", "CONST_", "MESSAGE_", "TALKTYPE_", "COMBAT_",
                        "CONDITION_", "SKULL_", "DIRECTION_", "RETURNVALUE_",
                        "FLUID_", "TEXTCOLOR_")):
                    continue
                # Skip if declared as local already or is a function param
                if var_name in locals_declared or var_name in func_params:
                    continue
                # Skip table field assignments (e.g., self.x = ...)
                if "." in stripped.split("=")[0] or "[" in stripped.split("=")[0]:
                    continue

                col = len(m.group(1)) + 1
                issues.append(LintIssue(
                    line=i,
                    column=col,
                    severity=self.severity,
                    rule_id=self.rule_id,
                    message=f"Variable '{var_name}' assigned without 'local' (possible global leak)",
                    suggestion=f"Add 'local' before '{var_name}'",
                    fixable=True,
                ))

        return issues


# ---------------------------------------------------------------------------
# Rule: hardcoded-id
# ---------------------------------------------------------------------------

class HardcodedIdRule(LintRule):
    """Detects hardcoded numeric item/monster IDs without named constants."""

    rule_id = "hardcoded-id"
    description = "Numeric IDs used directly instead of named constants"
    severity = LintSeverity.INFO

    # Functions commonly called with item/creature IDs
    ID_FUNCTIONS = {
        "addItem", "doPlayerAddItem", "doCreateItem", "doCreateMonster",
        "doCreateNpc", "removeItem", "doPlayerRemoveItem",
        "doTransformItem", "setStorageValue", "doPlayerSetStorageValue",
        "getStorageValue", "getPlayerStorageValue",
    }

    _call_pattern = re.compile(
        r'\b(\w+)\s*\(\s*(?:[^,)]+,\s*)?(\d{3,6})\b'
    )

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("--"):
                continue

            for match in self._call_pattern.finditer(line):
                func_name = match.group(1)
                numeric_id = match.group(2)

                # Only flag for known ID-related functions
                if not any(func_name.endswith(f) or func_name == f
                          for f in self.ID_FUNCTIONS):
                    continue

                # Skip storage IDs (typically > 10000)
                num_val = int(numeric_id)
                if num_val >= 10000:
                    continue

                col = match.start(2) + 1
                issues.append(LintIssue(
                    line=i,
                    column=col,
                    severity=self.severity,
                    rule_id=self.rule_id,
                    message=f"Hardcoded ID '{numeric_id}' used in {func_name}()",
                    suggestion="Consider using a named constant for readability",
                ))

        return issues


# ---------------------------------------------------------------------------
# Rule: deprecated-constant
# ---------------------------------------------------------------------------

class DeprecatedConstantRule(LintRule):
    """Detects deprecated/renamed constant names."""

    rule_id = "deprecated-constant"
    description = "Detects deprecated or renamed constants"
    severity = LintSeverity.WARNING

    def __init__(self):
        from ..mappings.constants import ALL_CONSTANTS

        # Only keep constants where old != new (actual renames)
        self._deprecated: Dict[str, str] = {}
        for old, new in ALL_CONSTANTS.items():
            if old != new:
                self._deprecated[old] = new

        if self._deprecated:
            escaped = [re.escape(c) for c in self._deprecated.keys()]
            self._pattern = re.compile(
                r'\b(' + '|'.join(escaped) + r')\b'
            )
        else:
            self._pattern = None

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []

        if not self._pattern:
            return issues

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("--"):
                continue

            for match in self._pattern.finditer(line):
                old_const = match.group(1)
                new_const = self._deprecated[old_const]
                col = match.start() + 1
                issues.append(LintIssue(
                    line=i,
                    column=col,
                    severity=self.severity,
                    rule_id=self.rule_id,
                    message=f"Deprecated constant: {old_const} → {new_const}",
                    suggestion=f"Replace with {new_const}",
                    fixable=True,
                ))

        return issues


# ---------------------------------------------------------------------------
# Rule: empty-callback
# ---------------------------------------------------------------------------

class EmptyCallbackRule(LintRule):
    """Detects callback functions with empty bodies."""

    rule_id = "empty-callback"
    description = "Callback function has an empty body"
    severity = LintSeverity.WARNING

    CALLBACKS = {
        "onUse", "onStepIn", "onStepOut", "onEquip", "onDeEquip",
        "onSay", "onLogin", "onLogout", "onDeath", "onKill",
        "onPrepareDeath", "onHealthChange", "onManaChange",
        "onTextEdit", "onThink", "onModalWindow", "onAddItem",
        "onRemoveItem", "onLook", "onCastSpell", "onStartup",
        "onShutdown", "onRecord", "onTime", "onTimer",
    }

    _func_pattern = re.compile(
        r'function\s+(?:\w+[.:])?(\w+)\s*\([^)]*\)\s*\n(.*?)\nend',
        re.DOTALL
    )

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []

        for match in self._func_pattern.finditer(code):
            func_name = match.group(1)
            if func_name not in self.CALLBACKS:
                continue

            body = match.group(2).strip()

            # Remove comments from body to check if truly empty
            body_no_comments = re.sub(r'--[^\n]*', '', body).strip()

            if not body_no_comments or body_no_comments in ("return true", "return false"):
                func_line = code[:match.start()].count("\n") + 1
                issues.append(LintIssue(
                    line=func_line,
                    column=1,
                    severity=self.severity,
                    rule_id=self.rule_id,
                    message=f"Callback '{func_name}' has an empty body",
                    suggestion="Add implementation or remove the callback",
                ))

        return issues


# ---------------------------------------------------------------------------
# Rule: mixed-api-style
# ---------------------------------------------------------------------------

class MixedApiStyleRule(LintRule):
    """Detects mixing procedural (TFS 0.3) and OOP (TFS 1.x) API in the same script."""

    rule_id = "mixed-api-style"
    description = "Script mixes old procedural API with modern OOP API"
    severity = LintSeverity.WARNING

    # Patterns indicating old procedural API
    _old_api_pattern = re.compile(
        r'\b(do(?:Player|Creature|Npc|Monster)\w+|'
        r'get(?:Player|Creature)\w+|'
        r'set(?:Player|Creature)\w+|'
        r'is(?:Player|Creature|Monster|Npc)\b)\s*\('
    )

    # Patterns indicating new OOP API
    _new_api_pattern = re.compile(
        r'\b(?:player|creature|item|monster|npc|tile|position)\s*[.:]\w+\s*\('
    )

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []

        old_api_lines: List[int] = []
        new_api_lines: List[int] = []

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("--"):
                continue

            if self._old_api_pattern.search(line):
                old_api_lines.append(i)
            if self._new_api_pattern.search(line):
                new_api_lines.append(i)

        if old_api_lines and new_api_lines:
            issues.append(LintIssue(
                line=old_api_lines[0],
                column=1,
                severity=self.severity,
                rule_id=self.rule_id,
                message=(
                    f"Script mixes old API ({len(old_api_lines)} calls) "
                    f"with new OOP API ({len(new_api_lines)} calls)"
                ),
                suggestion="Convert all code to the modern OOP API for consistency",
            ))

        return issues


# ---------------------------------------------------------------------------
# Rule: unsafe-storage
# ---------------------------------------------------------------------------

class UnsafeStorageRule(LintRule):
    """Detects setStorageValue without prior getStorageValue check."""

    rule_id = "unsafe-storage"
    description = "Storage value set without prior check/read"
    severity = LintSeverity.INFO

    _set_pattern = re.compile(
        r'(?:setStorageValue|doPlayerSetStorageValue|doCreatureSetStorage)\s*\([^,]+,\s*(\d+)'
    )
    _get_pattern = re.compile(
        r'(?:getStorageValue|getPlayerStorageValue|getCreatureStorage)\s*\([^,]+,\s*(\d+)'
    )

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []

        # Find all storage IDs that are read and written
        read_ids: Set[str] = set()
        for m in self._get_pattern.finditer(code):
            read_ids.add(m.group(1))

        for i, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("--"):
                continue

            for match in self._set_pattern.finditer(line):
                storage_id = match.group(1)
                if storage_id not in read_ids:
                    col = match.start() + 1
                    issues.append(LintIssue(
                        line=i,
                        column=col,
                        severity=self.severity,
                        rule_id=self.rule_id,
                        message=f"Storage {storage_id} is set but never read in this script",
                        suggestion="Consider checking the storage value before setting it",
                    ))

        return issues


# ---------------------------------------------------------------------------
# Registry of all rules
# ---------------------------------------------------------------------------

ALL_RULES: Dict[str, type] = {
    "deprecated-api": DeprecatedApiRule,
    "unused-parameter": UnusedParameterRule,
    "missing-return": MissingReturnRule,
    "invalid-callback-signature": InvalidCallbackSignatureRule,
    "global-variable-leak": GlobalVariableLeakRule,
    "hardcoded-id": HardcodedIdRule,
    "deprecated-constant": DeprecatedConstantRule,
    "empty-callback": EmptyCallbackRule,
    "mixed-api-style": MixedApiStyleRule,
    "unsafe-storage": UnsafeStorageRule,
}


def get_all_rules() -> List[LintRule]:
    """Instantiate and return all available lint rules."""
    return [cls() for cls in ALL_RULES.values()]


def get_rules_by_ids(rule_ids: List[str]) -> List[LintRule]:
    """Instantiate only the specified rules."""
    rules = []
    for rid in rule_ids:
        if rid in ALL_RULES:
            rules.append(ALL_RULES[rid]())
    return rules
