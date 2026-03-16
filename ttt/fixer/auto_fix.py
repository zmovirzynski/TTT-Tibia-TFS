"""
TTT Auto-Fixer — Automatic code correction engine.

Applies fixes for issues detected by the linter:
  - deprecated-api:              Replaces old procedural calls → OOP methods
  - missing-return:              Adds 'return true' at end of callbacks
  - global-variable-leak:        Prepends 'local' to bare assignments
  - deprecated-constant:         Replaces obsolete constant names
  - invalid-callback-signature:  Updates callback parameter lists

Reuses the existing LuaTransformer and mappings infrastructure.
"""

import os
import re
import shutil
import logging
import difflib
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field

from ..utils import read_file_safe, write_file_safe, find_lua_files, split_lua_args
from ..mappings.constants import ALL_CONSTANTS
from ..mappings.signatures import SIGNATURE_MAP, PARAM_RENAME_MAP
from ..linter.engine import LintEngine, LintConfig, FileLintResult, LintReport
from ..linter.rules import LintIssue, LintSeverity

logger = logging.getLogger("ttt")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FixAction:
    """A single fix applied to the code."""
    rule_id: str
    line: int
    description: str
    original: str = ""
    replacement: str = ""


@dataclass
class FileFixResult:
    """Result of fixing a single file."""
    filepath: str
    original_code: str = ""
    fixed_code: str = ""
    fixes: List[FixAction] = field(default_factory=list)
    error: str = ""
    backed_up: bool = False

    @property
    def changed(self) -> bool:
        return self.original_code != self.fixed_code

    @property
    def fix_count(self) -> int:
        return len(self.fixes)

    def diff_lines(self) -> List[str]:
        """Generate unified diff lines."""
        if not self.changed:
            return []
        orig = self.original_code.splitlines(keepends=True)
        fixed = self.fixed_code.splitlines(keepends=True)
        name = os.path.basename(self.filepath) if self.filepath else "code"
        return list(difflib.unified_diff(
            orig, fixed,
            fromfile=f"a/{name}",
            tofile=f"b/{name}",
            lineterm="",
        ))


@dataclass
class FixReport:
    """Aggregated fix report for all files."""
    files: List[FileFixResult] = field(default_factory=list)
    target_path: str = ""

    @property
    def total_fixes(self) -> int:
        return sum(f.fix_count for f in self.files)

    @property
    def files_changed(self) -> int:
        return sum(1 for f in self.files if f.changed)

    @property
    def files_unchanged(self) -> int:
        return sum(1 for f in self.files if not f.changed and not f.error)

    @property
    def files_errored(self) -> int:
        return sum(1 for f in self.files if f.error)

    @property
    def fix_summary(self) -> Dict[str, int]:
        """Count of fixes per rule_id."""
        counts: Dict[str, int] = {}
        for f in self.files:
            for fix in f.fixes:
                counts[fix.rule_id] = counts.get(fix.rule_id, 0) + 1
        return counts


# ---------------------------------------------------------------------------
# Individual fix functions
# ---------------------------------------------------------------------------

def fix_deprecated_api(code: str) -> Tuple[str, List[FixAction]]:
    """Replace deprecated TFS 0.3/0.4 procedural API calls with OOP equivalents."""
    from ..mappings.tfs03_functions import TFS03_TO_1X
    from ..mappings.tfs04_functions import TFS04_TO_1X

    # Combine all deprecated function maps
    all_funcs: Dict[str, Dict] = {}
    all_funcs.update(TFS03_TO_1X)
    for k, v in TFS04_TO_1X.items():
        if k not in all_funcs:
            all_funcs[k] = v

    fixes: List[FixAction] = []

    # Sort by name length (longest first) to avoid partial matches
    func_names = sorted(all_funcs.keys(), key=len, reverse=True)

    for func_name in func_names:
        mapping = all_funcs[func_name]
        escaped = re.escape(func_name)
        pattern = re.compile(
            r'(?<![.\w:])' + escaped + r'\s*\(',
            re.MULTILINE,
        )

        result_parts: List[str] = []
        last_end = 0
        search_start = 0

        while search_start < len(code):
            match = pattern.search(code, search_start)
            if not match:
                break

            call_start = match.start()

            # Skip if inside string or comment
            if _is_in_string_or_comment(code, call_start):
                search_start = match.end()
                continue

            # Find the opening paren and its matching close
            paren_start = code.index("(", call_start + len(func_name))
            paren_end = _find_matching_paren(code, paren_start)

            if paren_end is None:
                search_start = match.end()
                continue

            args_str = code[paren_start + 1:paren_end]
            args = split_lua_args(args_str)

            replacement = _generate_oop_replacement(func_name, args, mapping)

            if replacement and replacement != f"{func_name}({args_str})":
                line_num = code[:call_start].count("\n") + 1
                orig_text = code[call_start:paren_end + 1]

                fixes.append(FixAction(
                    rule_id="deprecated-api",
                    line=line_num,
                    description=f"{func_name}() -> {replacement}",
                    original=orig_text,
                    replacement=replacement,
                ))

                result_parts.append(code[last_end:call_start])
                result_parts.append(replacement)
                last_end = paren_end + 1
                search_start = last_end
            else:
                search_start = paren_end + 1 if paren_end else match.end()

        if result_parts:
            result_parts.append(code[last_end:])
            code = "".join(result_parts)

    return code, fixes


def fix_missing_return(code: str) -> Tuple[str, List[FixAction]]:
    """Add 'return true' to callback functions that don't have a return statement."""
    CALLBACKS = {
        "onUse", "onStepIn", "onStepOut", "onEquip", "onDeEquip",
        "onSay", "onLogin", "onLogout", "onDeath", "onKill",
        "onPrepareDeath", "onHealthChange", "onManaChange",
        "onTextEdit", "onThink", "onModalWindow", "onAddItem",
        "onRemoveItem", "onLook", "onTradeRequest", "onTradeAccept",
        "onCastSpell", "onTargetCreature", "onMoveCreature",
    }

    func_pattern = re.compile(
        r'function\s+(?:\w+[.:])?(\w+)\s*\([^)]*\)',
        re.MULTILINE,
    )

    fixes: List[FixAction] = []
    # We need to work backwards to avoid offset shifts
    matches_to_fix: List[Tuple[int, str, int]] = []  # (end_pos_of_end_keyword, func_name, func_line)

    for match in func_pattern.finditer(code):
        func_name = match.group(1)
        if func_name not in CALLBACKS:
            continue

        func_start = match.end()
        # Find the matching 'end' for this function
        end_pos = _find_function_end(code, func_start)
        if end_pos is None:
            continue

        # Extract body between func declaration and 'end'
        body = code[func_start:end_pos]

        # Check if there's any return statement
        if re.search(r'\breturn\b', body):
            continue

        func_line = code[:match.start()].count("\n") + 1
        matches_to_fix.append((end_pos, func_name, func_line))

    # Apply fixes in reverse order (bottom-up) to preserve positions
    matches_to_fix.sort(key=lambda x: x[0], reverse=True)

    for end_pos, func_name, func_line in matches_to_fix:
        # Find indent of the 'end' keyword
        line_start = code.rfind("\n", 0, end_pos)
        if line_start == -1:
            line_start = 0
        else:
            line_start += 1

        end_line_text = code[line_start:end_pos]
        indent = ""
        for ch in end_line_text:
            if ch in (" ", "\t"):
                indent += ch
            else:
                break

        # Determine inner indent (one level deeper than 'end')
        inner_indent = indent + "    "

        # Insert 'return true' before the 'end' line
        insertion = f"{inner_indent}return true\n"
        code = code[:end_pos] + insertion + code[end_pos:]

        fixes.append(FixAction(
            rule_id="missing-return",
            line=func_line,
            description=f"Added 'return true' to callback '{func_name}'",
            original="end",
            replacement=f"    return true\nend",
        ))

    return code, fixes


def fix_global_variable_leak(code: str) -> Tuple[str, List[FixAction]]:
    """Add 'local' keyword before variable assignments that lack it."""
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
    }

    # Collect all local declarations and function params to know what's already local
    local_vars: Set[str] = set()
    # local x = ...
    for m in re.finditer(r'\blocal\s+(\w+)', code):
        local_vars.add(m.group(1))
    # function params
    for m in re.finditer(r'function\s+\w*\s*\(([^)]*)\)', code):
        params = [p.strip() for p in m.group(1).split(",") if p.strip()]
        local_vars.update(params)
    # for loop vars
    for m in re.finditer(r'\bfor\s+(\w+)', code):
        local_vars.add(m.group(1))

    fixes: List[FixAction] = []
    lines = code.split("\n")
    new_lines: List[str] = []

    for i, line in enumerate(lines):
        stripped = line.lstrip()

        # Skip comments, empty lines
        if not stripped or stripped.startswith("--"):
            new_lines.append(line)
            continue

        # Skip lines that already have 'local'
        if stripped.startswith("local "):
            new_lines.append(line)
            continue

        # Skip function declarations
        if stripped.startswith("function "):
            new_lines.append(line)
            continue

        # Skip return, end, if, for, while, etc.
        if re.match(r'^(return|end|if|elseif|else|for|while|repeat|until|do)\b', stripped):
            new_lines.append(line)
            continue

        # Match: varname = expr (but not == ~= <= >= comparisons)
        m = re.match(r'^(\s*)(\w+)\s*=\s*(?!=)', line)
        if m:
            indent = m.group(1)
            var_name = m.group(2)

            # Skip known globals, already-local vars, uppercase constants
            if (var_name in KNOWN_GLOBALS or
                    var_name in local_vars or
                    var_name.isupper() or
                    var_name.startswith("ITEM_") or
                    var_name.startswith("CONST_") or
                    var_name.startswith("MESSAGE_") or
                    var_name.startswith("TALKTYPE_") or
                    var_name.startswith("COMBAT_") or
                    var_name.startswith("CONDITION_")):
                new_lines.append(line)
                continue

            # Check if it's a table field assignment (e.g. self.x = ...)
            # or method definition — these are fine as-is
            rest_of_line = line[m.end():]
            # Make sure there's no dot/colon before the var in context
            pre_indent = line[:m.start(2)]
            if pre_indent.rstrip().endswith((".",":", "[")):
                new_lines.append(line)
                continue

            # Add 'local'
            new_line = f"{indent}local {var_name}" + line[m.end(2):]
            new_lines.append(new_line)
            local_vars.add(var_name)  # track so we don't double-fix

            fixes.append(FixAction(
                rule_id="global-variable-leak",
                line=i + 1,
                description=f"Added 'local' before '{var_name}'",
                original=line.strip(),
                replacement=new_line.strip(),
            ))
        else:
            new_lines.append(line)

    return "\n".join(new_lines), fixes


def fix_deprecated_constants(code: str) -> Tuple[str, List[FixAction]]:
    """Replace deprecated constants with their modern equivalents."""
    changes = {k: v for k, v in ALL_CONSTANTS.items() if k != v}
    if not changes:
        return code, []

    fixes: List[FixAction] = []

    for old_const, new_const in changes.items():
        if old_const not in code:
            continue

        # Track lines where replacements happen before applying
        lines = code.split("\n")
        for i, line in enumerate(lines):
            stripped = line.lstrip()
            if stripped.startswith("--"):
                continue
            if old_const in line:
                # Verify it's a whole-word match
                pattern = re.compile(r'\b' + re.escape(old_const) + r'\b')
                if pattern.search(line):
                    fixes.append(FixAction(
                        rule_id="deprecated-constant",
                        line=i + 1,
                        description=f"{old_const} -> {new_const}",
                        original=old_const,
                        replacement=new_const,
                    ))

        # Apply the replacement (whole-word, outside strings)
        code = _replace_word_outside_strings(code, old_const, new_const)

    return code, fixes


def fix_invalid_callback_signature(code: str) -> Tuple[str, List[FixAction]]:
    """Update callback signatures to match the expected TFS 1.x parameter lists."""
    func_pattern = re.compile(
        r'(function\s+(?:\w+[.:])?)'   # prefix
        r'(\w+)'                         # event name
        r'\s*\(([^)]*)\)',               # (params)
        re.MULTILINE,
    )

    fixes: List[FixAction] = []
    var_renames: Dict[str, str] = {}

    def replace_sig(match):
        prefix = match.group(1)
        event_name = match.group(2)
        old_params_str = match.group(3)
        old_params = [p.strip() for p in old_params_str.split(",") if p.strip()]

        if event_name not in SIGNATURE_MAP:
            return match.group(0)

        old_sig, new_sig = SIGNATURE_MAP[event_name]
        new_params = new_sig["params"]

        # Already has the new signature?
        if old_params == new_params:
            return match.group(0)

        # Match against old signature variants
        all_old = [old_sig["params"]] + old_sig.get("alt_params", [])
        matched_old = None
        for variant in all_old:
            if len(old_params) == len(variant):
                matched_old = variant
                break

        if matched_old is None:
            # Param count doesn't match any known old variant — skip
            return match.group(0)

        # Build rename map for variable references in the body
        for i, old_p in enumerate(matched_old):
            if i < len(new_params) and old_p != new_params[i]:
                var_renames[old_p] = new_params[i]

        func_line = code[:match.start()].count("\n") + 1
        new_params_str = ", ".join(new_params)

        fixes.append(FixAction(
            rule_id="invalid-callback-signature",
            line=func_line,
            description=f"{event_name}({old_params_str}) -> {event_name}({new_params_str})",
            original=f"{prefix}{event_name}({old_params_str})",
            replacement=f"{prefix}{event_name}({new_params_str})",
        ))

        return f"{prefix}{event_name}({new_params_str})"

    code = func_pattern.sub(replace_sig, code)

    # Also rename variables in the body
    if var_renames:
        code = _rename_variables_in_code(code, var_renames)

    return code, fixes


# ---------------------------------------------------------------------------
# Helpers (reused from LuaTransformer patterns)
# ---------------------------------------------------------------------------

def _generate_oop_replacement(func_name: str, args: List[str],
                               mapping: Dict) -> Optional[str]:
    """Generate the OOP replacement for a deprecated function call."""
    method = mapping.get("method")
    obj_type = mapping.get("obj_type")
    obj_param = mapping.get("obj_param", 0)
    drop_params = mapping.get("drop_params", [0])
    is_static = mapping.get("static", False)
    static_class = mapping.get("static_class")
    wrapper = mapping.get("wrapper")
    custom = mapping.get("custom")

    if custom:
        return _handle_custom(custom, func_name, args, mapping)

    if method is None:
        args_str = ", ".join(args)
        return f"{func_name}({args_str})"

    if is_static and static_class:
        args_str = ", ".join(args)
        return f"{static_class}.{method}({args_str})"

    if obj_param is not None and obj_param < len(args):
        obj_arg = args[obj_param].strip()
        obj_var = _resolve_object_var(obj_arg, obj_type, wrapper)

        remaining = [a for i, a in enumerate(args) if i not in drop_params]
        remaining_str = ", ".join(remaining)

        return f"{obj_var}:{method}({remaining_str})"

    args_str = ", ".join(args)
    return f"{func_name}({args_str})"


def _resolve_object_var(arg: str, obj_type: str,
                        wrapper: Optional[str] = None) -> str:
    """Resolve argument to its OOP object variable name."""
    renamed = PARAM_RENAME_MAP.get(arg)
    if renamed:
        return renamed

    if arg == obj_type or arg in ("player", "creature", "item", "npc", "monster"):
        return arg

    if wrapper:
        if wrapper == "Position":
            if ":getPosition()" in arg or ":getClosestFreePosition()" in arg:
                return arg
            arg_lower = arg.lower()
            if any(name in arg_lower for name in ("position", "pos", "dest")):
                return arg
        return f"{wrapper}({arg})"

    type_constructors = {
        "player": "Player",
        "creature": "Creature",
        "item": "Item",
        "tile": "Tile",
        "position": "Position",
        "house": "House",
        "town": "Town",
        "npc": "Npc",
        "monster": "Monster",
        "container": "Container",
    }

    constructor = type_constructors.get(obj_type)
    if constructor and arg != obj_type:
        if arg in ("player", "creature", "self", "target"):
            return arg
        return f"{constructor}({arg})"

    return arg


def _handle_custom(custom_type: str, func_name: str, args: List[str],
                   mapping: Dict) -> Optional[str]:
    """Handle custom mapping types."""
    if custom_type == "type_check":
        cls = mapping.get("custom_class", "Creature")
        if args:
            arg = args[0].strip()
            renamed = PARAM_RENAME_MAP.get(arg, arg)
            if renamed in ("player", "creature", "target"):
                return f"{renamed}:is{cls}()"
            return f"{cls}({arg}) ~= nil"
        return f"{func_name}()"

    if custom_type == "vocation_check":
        if args:
            arg = args[0].strip()
            renamed = PARAM_RENAME_MAP.get(arg, arg)
            return f"{renamed}:getVocation():getId()"
        return f"{func_name}()"

    if custom_type == "item_type_getter":
        method = mapping.get("method", "getName")
        if args:
            return f"ItemType({args[0].strip()}):{method}()"
        return f"ItemType():{method}()"

    if custom_type == "item_type_by_name":
        if args:
            return f"ItemType({args[0].strip()}):getId()"
        return f"ItemType():getId()"

    if custom_type == "combat_passthrough":
        args_str = ", ".join(args)
        return f"{func_name}({args_str})"

    if custom_type == "house_lookup":
        if args:
            return f"House({args[0].strip()})"
        return f"House()"

    if custom_type == "npc_self":
        args_str = ", ".join(args)
        return f"selfSay({args_str})"

    if custom_type == "npc_passthrough":
        args_str = ", ".join(args)
        return f"{func_name}({args_str})"

    if custom_type == "npc_get_self":
        return "Npc()"

    if custom_type == "npc_method_self":
        method = mapping.get("method", "getName")
        return f"Npc():{method}()"

    if custom_type == "npc_action_self":
        method = mapping.get("method", "move")
        args_str = ", ".join(args)
        return f"Npc():{method}({args_str})"

    args_str = ", ".join(args)
    return f"{func_name}({args_str})"


def _rename_variables_in_code(code: str, var_renames: Dict[str, str]) -> str:
    """Rename variables throughout the code, respecting strings and comments."""
    lines = code.split("\n")
    result: List[str] = []

    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("--"):
            result.append(line)
            continue

        code_part, comment_part = _split_code_comment(line)

        for old_name, new_name in var_renames.items():
            if old_name in code_part:
                code_part = _replace_word_outside_strings(code_part, old_name, new_name)

        result.append(code_part + comment_part)

    return "\n".join(result)


def _split_code_comment(line: str) -> Tuple[str, str]:
    """Split a line into code and comment parts."""
    in_string = None
    i = 0
    while i < len(line):
        ch = line[i]
        if in_string:
            if ch == "\\" and i + 1 < len(line):
                i += 2
                continue
            if ch == in_string:
                in_string = None
        else:
            if ch in ('"', "'"):
                in_string = ch
            elif ch == "-" and i + 1 < len(line) and line[i + 1] == "-":
                return line[:i], line[i:]
        i += 1
    return line, ""


def _replace_word_outside_strings(text: str, old: str, new: str) -> str:
    """Replace whole-word occurrences of old with new, skipping strings."""
    result_parts: List[str] = []
    i = 0
    in_string = None

    while i < len(text):
        ch = text[i]

        if in_string:
            result_parts.append(ch)
            if ch == "\\" and i + 1 < len(text):
                result_parts.append(text[i + 1])
                i += 2
                continue
            if ch == in_string:
                in_string = None
            i += 1
            continue

        if ch in ('"', "'"):
            in_string = ch
            result_parts.append(ch)
            i += 1
            continue

        if ch == "[" and i + 1 < len(text) and text[i + 1] == "[":
            end = text.find("]]", i + 2)
            if end != -1:
                result_parts.append(text[i:end + 2])
                i = end + 2
                continue

        if text[i:i + len(old)] == old:
            before_ok = (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_"))
            after_pos = i + len(old)
            after_ok = (after_pos >= len(text) or
                        not (text[after_pos].isalnum() or text[after_pos] == "_"))
            if before_ok and after_ok:
                result_parts.append(new)
                i += len(old)
                continue

        result_parts.append(ch)
        i += 1

    return "".join(result_parts)


def _is_in_string_or_comment(code: str, pos: int) -> bool:
    """Check if the given position is inside a string literal or comment."""
    line_start = code.rfind("\n", 0, pos)
    if line_start == -1:
        line_start = 0
    else:
        line_start += 1

    line_text = code[line_start:pos]
    in_string = None

    for i, ch in enumerate(line_text):
        if in_string:
            if ch == "\\" and i + 1 < len(line_text):
                continue
            if ch == in_string:
                in_string = None
            continue
        if ch in ('"', "'"):
            in_string = ch
            continue
        if ch == "-" and i + 1 < len(line_text) and line_text[i + 1] == "-":
            return True

    return in_string is not None


def _find_matching_paren(code: str, paren_start: int) -> Optional[int]:
    """Find the position of the closing paren matching the one at paren_start."""
    depth = 1
    i = paren_start + 1
    in_string = None

    while i < len(code) and depth > 0:
        ch = code[i]

        if in_string and ch == "\\" and i + 1 < len(code):
            i += 2
            continue

        if ch in ('"', "'"):
            if in_string is None:
                in_string = ch
            elif in_string == ch:
                in_string = None
            i += 1
            continue

        if not in_string and ch == "[" and i + 1 < len(code) and code[i + 1] == "[":
            end = code.find("]]", i + 2)
            if end != -1:
                i = end + 2
                continue

        if not in_string:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1

        i += 1

    return (i - 1) if depth == 0 else None


def _find_function_end(code: str, start: int) -> Optional[int]:
    """Find the position of the 'end' keyword matching the function starting at start."""
    depth = 1
    i = start
    in_string = None

    while i < len(code):
        ch = code[i]

        # Skip comments
        if not in_string and code[i:i + 2] == "--":
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
                return i
            i += m.end()
            continue

        i += 1

    return None


# ---------------------------------------------------------------------------
# Fix Engine
# ---------------------------------------------------------------------------

# Ordered list of fixers — order matters (signature fix should come before
# deprecated-api so renamed params are available)
FIXERS = [
    ("invalid-callback-signature", fix_invalid_callback_signature),
    ("deprecated-api", fix_deprecated_api),
    ("deprecated-constant", fix_deprecated_constants),
    ("missing-return", fix_missing_return),
    ("global-variable-leak", fix_global_variable_leak),
]

FIXABLE_RULES = {fixer_id for fixer_id, _ in FIXERS}


class FixEngine:
    """Main fix engine that applies auto-corrections to Lua scripts."""

    def __init__(self, config: Optional[LintConfig] = None,
                 dry_run: bool = False,
                 create_backup: bool = True,
                 enabled_fixes: Optional[List[str]] = None):
        self.config = config or LintConfig()
        self.dry_run = dry_run
        self.create_backup = create_backup
        self.enabled_fixes = set(enabled_fixes) if enabled_fixes else FIXABLE_RULES

    def fix_code(self, code: str, filename: str = "") -> FileFixResult:
        """Apply all enabled fixes to a string of Lua code."""
        result = FileFixResult(filepath=filename, original_code=code)
        current_code = code

        for fixer_id, fixer_fn in FIXERS:
            if fixer_id not in self.enabled_fixes:
                continue
            try:
                current_code, fixes = fixer_fn(current_code)
                result.fixes.extend(fixes)
            except Exception as e:
                logger.warning(f"Fixer '{fixer_id}' failed on {filename}: {e}")

        result.fixed_code = current_code
        return result

    def fix_file(self, filepath: str) -> FileFixResult:
        """Fix a single Lua file."""
        code = read_file_safe(filepath)
        if code is None:
            return FileFixResult(
                filepath=filepath,
                error=f"Could not read file: {filepath}",
            )

        result = self.fix_code(code, os.path.basename(filepath))
        result.filepath = filepath

        if result.changed and not self.dry_run:
            # Create backup
            if self.create_backup:
                backup_path = filepath + ".bak"
                try:
                    shutil.copy2(filepath, backup_path)
                    result.backed_up = True
                    logger.debug(f"  Backup: {backup_path}")
                except OSError as e:
                    logger.warning(f"  Could not create backup: {e}")

            # Write fixed code
            write_file_safe(filepath, result.fixed_code)
            logger.debug(f"  Fixed: {filepath} ({result.fix_count} fixes)")

        return result

    def fix_directory(self, directory: str) -> FixReport:
        """Fix all Lua files in a directory."""
        report = FixReport(target_path=os.path.abspath(directory))

        lua_files = find_lua_files(directory)
        if not lua_files:
            logger.info(f"No Lua files found in {directory}")
            return report

        mode = "DRY-RUN" if self.dry_run else "FIXING"
        logger.info(f"{mode} {len(lua_files)} files in {directory}...")

        for filepath in lua_files:
            result = self.fix_file(filepath)
            report.files.append(result)

            if result.changed:
                logger.debug(f"  {os.path.relpath(filepath, directory)}: "
                             f"{result.fix_count} fixes applied")
            else:
                logger.debug(f"  {os.path.relpath(filepath, directory)}: no changes")

        return report


# ---------------------------------------------------------------------------
# Report formatters
# ---------------------------------------------------------------------------

def format_fix_text(report: FixReport, base_dir: str,
                    use_colors: bool = True, show_diff: bool = False) -> str:
    """Format fix report as human-readable text."""
    lines: List[str] = []

    # ANSI colors
    if use_colors:
        GREEN = "\033[32m"
        YELLOW = "\033[33m"
        RED = "\033[31m"
        CYAN = "\033[36m"
        DIM = "\033[2m"
        BOLD = "\033[1m"
        RESET = "\033[0m"
    else:
        GREEN = YELLOW = RED = CYAN = DIM = BOLD = RESET = ""

    for file_result in report.files:
        if file_result.error:
            rel = os.path.relpath(file_result.filepath, base_dir)
            lines.append(f"{RED}{rel}{RESET}")
            lines.append(f"  {RED}ERROR: {file_result.error}{RESET}")
            lines.append("")
            continue

        if not file_result.changed:
            continue

        rel = os.path.relpath(file_result.filepath, base_dir)
        lines.append(f"{BOLD}{rel}{RESET}")

        for fix in file_result.fixes:
            rule_color = GREEN
            lines.append(
                f"  {DIM}L{fix.line:<5d}{RESET} "
                f"{rule_color}{fix.rule_id:<30s}{RESET} "
                f"{fix.description}"
            )

        if show_diff and file_result.changed:
            lines.append("")
            for diff_line in file_result.diff_lines():
                if diff_line.startswith("+") and not diff_line.startswith("+++"):
                    lines.append(f"  {GREEN}{diff_line}{RESET}")
                elif diff_line.startswith("-") and not diff_line.startswith("---"):
                    lines.append(f"  {RED}{diff_line}{RESET}")
                elif diff_line.startswith("@@"):
                    lines.append(f"  {CYAN}{diff_line}{RESET}")
                else:
                    lines.append(f"  {diff_line}")

        if file_result.backed_up:
            lines.append(f"  {DIM}(backup: {rel}.bak){RESET}")

        lines.append("")

    # Summary
    sep = "=" * 60
    lines.append(sep)
    lines.append(f"{BOLD}Summary{RESET}")
    lines.append("-" * 60)
    lines.append(f"  Files scanned:    {len(report.files)}")
    lines.append(f"  Files fixed:      {BOLD}{report.files_changed}{RESET}")
    lines.append(f"  Files unchanged:  {report.files_unchanged}")
    if report.files_errored:
        lines.append(f"  Files with errors: {RED}{report.files_errored}{RESET}")
    lines.append("")
    lines.append(f"  Total fixes:      {BOLD}{report.total_fixes}{RESET}")

    summary = report.fix_summary
    if summary:
        lines.append("")
        lines.append("  Fixes by rule:")
        for rule_id, count in sorted(summary.items(), key=lambda x: -x[1]):
            lines.append(f"    {rule_id:<30s} {count}")

    lines.append(sep)

    return "\n".join(lines)


def format_fix_json(report: FixReport, base_dir: str) -> str:
    """Format fix report as JSON."""
    import json

    data = {
        "target": report.target_path,
        "summary": {
            "files_scanned": len(report.files),
            "files_fixed": report.files_changed,
            "files_unchanged": report.files_unchanged,
            "total_fixes": report.total_fixes,
            "fixes_by_rule": report.fix_summary,
        },
        "files": [],
    }

    for f in report.files:
        entry: Dict = {
            "path": os.path.relpath(f.filepath, base_dir),
            "changed": f.changed,
            "fix_count": f.fix_count,
        }
        if f.error:
            entry["error"] = f.error
        if f.fixes:
            entry["fixes"] = [
                {
                    "rule": fix.rule_id,
                    "line": fix.line,
                    "description": fix.description,
                }
                for fix in f.fixes
            ]
        data["files"].append(entry)

    return json.dumps(data, indent=2, ensure_ascii=False)
