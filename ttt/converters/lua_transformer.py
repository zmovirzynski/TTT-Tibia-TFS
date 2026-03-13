"""Motor de transformação Lua (API procedural → OOP)."""

import re
import logging
from typing import Dict, List, Optional, Tuple, Set

from ..utils import split_lua_args
from ..mappings.constants import ALL_CONSTANTS
from ..mappings.signatures import SIGNATURE_MAP, PARAM_RENAME_MAP

logger = logging.getLogger("ttt")

class LuaTransformer:

    def __init__(self, function_map: Dict, source_version: str = "tfs03"):
        self.function_map = function_map
        self.source_version = source_version
        self.warnings: List[str] = []
        self.stats = {
            "functions_converted": 0,
            "signatures_updated": 0,
            "constants_replaced": 0,
            "variables_renamed": 0,
        }

    def transform(self, code: str, filename: str = "") -> str:
        self.warnings = []
        self.stats = {k: 0 for k in self.stats}

        code, var_renames = self._transform_signatures(code)

        code = self._rename_variables(code, var_renames)

        code = self._transform_function_calls(code, var_renames)

        code = self._replace_constants(code)

        code = self._transform_positions(code)

        code = self._cleanup(code)

        if self.warnings:
            logger.debug(f"  Warnings for {filename}:")
            for w in self.warnings:
                logger.debug(f"    - {w}")

        return code

    def _transform_signatures(self, code: str) -> Tuple[str, Dict[str, str]]:
        var_renames: Dict[str, str] = {}

        # Pattern to match: function onXxx(params)
        # Also matches: function eventName.onXxx(params)
        pattern = re.compile(
            r'(function\s+(?:\w+[.:])?)'   # "function " or "function name."
            r'(\w+)'                         # event name (onUse, onLogin, etc.)
            r'\s*\(([^)]*)\)',              # (params)
            re.MULTILINE
        )

        def replace_signature(match):
            prefix = match.group(1)
            event_name = match.group(2)
            old_params_str = match.group(3)
            old_params = [p.strip() for p in old_params_str.split(",") if p.strip()]

            if event_name not in SIGNATURE_MAP:
                return match.group(0)

            old_sig, new_sig = SIGNATURE_MAP[event_name]
            new_params = new_sig["params"]

            # Check if old params match any known old signature
            all_old_variants = [old_sig["params"]] + old_sig.get("alt_params", [])
            matched = False
            matched_old = None

            for variant in all_old_variants:
                if len(old_params) == len(variant):
                    matched = True
                    matched_old = variant
                    break

            if not matched:
                # Params don't match any known old signature
                # Still try to update if param count is close
                if old_params and old_params != new_params:
                    self.warnings.append(
                        f"Signature '{event_name}({old_params_str})' doesn't match "
                        f"known patterns. Updating to new signature anyway."
                    )
                    matched_old = old_params
                else:
                    return match.group(0)

            # Build variable rename mapping from old → new
            if matched_old:
                for i, old_p in enumerate(matched_old):
                    if i < len(new_params) and old_p != new_params[i]:
                        var_renames[old_p] = new_params[i]

            self.stats["signatures_updated"] += 1
            new_params_str = ", ".join(new_params)
            return f"{prefix}{event_name}({new_params_str})"

        code = pattern.sub(replace_signature, code)
        return code, var_renames

    def _rename_variables(self, code: str, var_renames: Dict[str, str]) -> str:
        if not var_renames:
            return code

        lines = code.split("\n")
        result_lines = []

        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith("--"):
                result_lines.append(line)
                continue

            code_part, comment_part = self._split_code_comment(line)

            for old_name, new_name in var_renames.items():
                if old_name in code_part:
                    # Replace whole-word occurrences outside strings
                    code_part = self._replace_word_outside_strings(
                        code_part, old_name, new_name
                    )
                    self.stats["variables_renamed"] += 1

            result_lines.append(code_part + comment_part)

        return "\n".join(result_lines)

    def _split_code_comment(self, line: str) -> Tuple[str, str]:
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

    def _replace_word_outside_strings(self, text: str, old: str, new: str) -> str:
        # Use word boundary regex but respect Lua string contexts
        result = []
        i = 0
        in_string = None

        while i < len(text):
            ch = text[i]

            if in_string:
                result.append(ch)
                if ch == "\\" and i + 1 < len(text):
                    result.append(text[i + 1])
                    i += 2
                    continue
                if ch == in_string:
                    in_string = None
                i += 1
                continue

            if ch in ('"', "'"):
                in_string = ch
                result.append(ch)
                i += 1
                continue

            if ch == "[" and i + 1 < len(text) and text[i + 1] == "[":
                end = text.find("]]", i + 2)
                if end != -1:
                    result.append(text[i:end + 2])
                    i = end + 2
                    continue

            if text[i:i + len(old)] == old:
                before_ok = (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_"))
                after_pos = i + len(old)
                after_ok = (after_pos >= len(text) or not (text[after_pos].isalnum() or text[after_pos] == "_"))

                if before_ok and after_ok:
                    result.append(new)
                    i += len(old)
                    continue

            result.append(ch)
            i += 1

        return "".join(result)

    def _transform_function_calls(self, code: str, var_renames: Dict[str, str]) -> str:
        func_names = sorted(self.function_map.keys(), key=len, reverse=True)

        if not func_names:
            return code

        for func_name in func_names:
            mapping = self.function_map[func_name]
            code = self._replace_function(code, func_name, mapping, var_renames)

        return code

    def _replace_function(self, code: str, func_name: str, mapping: Dict,
                          var_renames: Dict[str, str]) -> str:
        escaped_name = re.escape(func_name)
        pattern = re.compile(
            r'(?<![.\w:])' + escaped_name + r'\s*\(',
            re.MULTILINE
        )

        result = []
        last_end = 0
        search_start = 0

        while search_start < len(code):
            match = pattern.search(code, search_start)
            if not match:
                break

            call_start = match.start()

            if self._is_in_string_or_comment(code, call_start):
                search_start = match.end()
                continue

            paren_start = code.index("(", call_start + len(func_name))
            paren_end = self._find_matching_paren(code, paren_start)

            if paren_end is None:
                search_start = match.end()
                continue

            args_str = code[paren_start + 1:paren_end]
            args = split_lua_args(args_str)

            replacement, note = self._generate_replacement(
                func_name, args, mapping, var_renames
            )

            if replacement is None:
                search_start = paren_end + 1
                continue

            full_replacement = replacement
            if note:
                # Add note on the line before
                # Find start of current line
                line_start = code.rfind("\n", 0, call_start)
                indent = ""
                if line_start != -1:
                    line_text = code[line_start + 1:call_start]
                    indent = ""
                    for ch in line_text:
                        if ch in (" ", "\t"):
                            indent += ch
                        else:
                            break
                # We'll add the note as inline comment after the replacement
                full_replacement = replacement + "  " + note

            result.append(code[last_end:call_start])
            result.append(full_replacement)
            last_end = paren_end + 1
            search_start = last_end
            self.stats["functions_converted"] += 1

        result.append(code[last_end:])
        return "".join(result)

    def _generate_replacement(self, func_name: str, args: List[str],
                               mapping: Dict, var_renames: Dict[str, str]) -> Tuple[Optional[str], Optional[str]]:
        method = mapping.get("method")
        obj_type = mapping.get("obj_type")
        obj_param = mapping.get("obj_param", 0)
        drop_params = mapping.get("drop_params", [0])
        is_static = mapping.get("static", False)
        static_class = mapping.get("static_class")
        wrapper = mapping.get("wrapper")
        note = mapping.get("note")
        custom = mapping.get("custom")

        if custom:
            return self._handle_custom(custom, func_name, args, mapping, var_renames), note

        if method is None:
            # No direct mapping, add a comment
            args_str = ", ".join(args)
            return f"{func_name}({args_str})", note

        if is_static and static_class:
            args_str = ", ".join(args)
            return f"{static_class}.{method}({args_str})", note

        if obj_param is not None and obj_param < len(args):
            obj_arg = args[obj_param].strip()

            # Determine the object variable name
            obj_var = self._resolve_object_var(obj_arg, obj_type, var_renames, wrapper)

            remaining = [a for i, a in enumerate(args) if i not in drop_params]
            remaining_str = ", ".join(remaining)

            return f"{obj_var}:{method}({remaining_str})", note
        elif obj_param is None and not is_static:
            args_str = ", ".join(args)
            return f"{func_name}({args_str})", note

        # Fallback
        args_str = ", ".join(args)
        return f"{func_name}({args_str})", note

    def _resolve_object_var(self, arg: str, obj_type: str,
                            var_renames: Dict[str, str],
                            wrapper: Optional[str] = None) -> str:
        renamed = var_renames.get(arg)
        if renamed:
            return renamed

        global_rename = PARAM_RENAME_MAP.get(arg)
        if global_rename:
            return global_rename

        if arg == obj_type or arg in ("player", "creature", "item", "npc", "monster"):
            return arg

        if wrapper:
            # Don't wrap if arg is already a method call that returns the right type
            if wrapper == "Position":
                # Known position variable names or method calls returning Position
                if ":getPosition()" in arg or ":getClosestFreePosition()" in arg:
                    return arg
                # Check if variable name suggests it's already a Position
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
            # If arg is a simple variable, maybe it's already the right type
            # In many cases after signature update, 'player' will be a Player object
            if arg in ("player", "creature", "self", "target"):
                return arg
            # Otherwise wrap it
            return f"{constructor}({arg})"

        return arg

    def _handle_custom(self, custom_type: str, func_name: str, args: List[str],
                       mapping: Dict, var_renames: Dict[str, str]) -> Optional[str]:
        if custom_type == "type_check":
            cls = mapping.get("custom_class", "Creature")
            if args:
                arg = args[0].strip()
                renamed = var_renames.get(arg, PARAM_RENAME_MAP.get(arg, arg))
                return f"{renamed}:is{cls}()" if renamed in ("player", "creature", "target") else f"{cls}({arg}) ~= nil"
            return f"{func_name}()"

        if custom_type == "vocation_check":
            if args:
                arg = args[0].strip()
                renamed = var_renames.get(arg, PARAM_RENAME_MAP.get(arg, arg))
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
            note = mapping.get("note", "")
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
            # getNpcCid() → Npc() (self-reference in NPC context)
            return "Npc()"

        if custom_type == "npc_method_self":
            # getNpcName() → Npc():getName(), getNpcPos() → Npc():getPosition()
            method = mapping.get("method", "getName")
            return f"Npc():{method}()"

        if custom_type == "npc_action_self":
            # selfMoveTo(pos) → Npc():move(pos), selfTurn(dir) → Npc():turn(dir)
            method = mapping.get("method", "move")
            args_str = ", ".join(args)
            return f"Npc():{method}({args_str})"

        args_str = ", ".join(args)
        return f"{func_name}({args_str})"

    def _replace_constants(self, code: str) -> str:
        changes = {k: v for k, v in ALL_CONSTANTS.items() if k != v}

        if not changes:
            return code

        for old_const, new_const in changes.items():
            if old_const not in code:
                continue

            # Replace whole-word only, outside strings
            code = self._replace_word_outside_strings(code, old_const, new_const)
            self.stats["constants_replaced"] += 1

        return code

    def _transform_positions(self, code: str) -> str:
        pattern = re.compile(
            r'\{\s*x\s*=\s*(\w+)\s*,\s*y\s*=\s*(\w+)\s*,\s*z\s*=\s*(\w+)\s*\}',
            re.IGNORECASE
        )

        def replace_pos(match):
            x, y, z = match.group(1), match.group(2), match.group(3)
            return f"Position({x}, {y}, {z})"

        code = pattern.sub(replace_pos, code)

        pattern2 = re.compile(
            r'\{\s*x\s*=\s*(\w+)\s*,\s*y\s*=\s*(\w+)\s*,\s*z\s*=\s*(\w+)\s*,'
            r'\s*stackpos\s*=\s*(\w+)\s*\}',
            re.IGNORECASE
        )

        def replace_pos_stack(match):
            x, y, z = match.group(1), match.group(2), match.group(3)
            stackpos = match.group(4)
            return f"Position({x}, {y}, {z})"  # stackpos not needed in 1.x Position

        code = pattern2.sub(replace_pos_stack, code)

        return code

    def _cleanup(self, code: str) -> str:
        while "\n\n\n" in code:
            code = code.replace("\n\n\n", "\n\n")

        return code

    # Helper methods

    def _is_in_string_or_comment(self, code: str, pos: int) -> bool:
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

    def _find_matching_paren(self, code: str, paren_start: int) -> Optional[int]:
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

        if depth == 0:
            return i - 1  # position of closing paren

        return None

    def get_summary(self) -> str:
        parts = []
        if self.stats["signatures_updated"]:
            parts.append(f"{self.stats['signatures_updated']} signature(s) updated")
        if self.stats["functions_converted"]:
            parts.append(f"{self.stats['functions_converted']} function call(s) converted")
        if self.stats["constants_replaced"]:
            parts.append(f"{self.stats['constants_replaced']} constant(s) replaced")
        if self.stats["variables_renamed"]:
            parts.append(f"{self.stats['variables_renamed']} variable(s) renamed")
        if self.warnings:
            parts.append(f"{len(self.warnings)} warning(s)")
        return ", ".join(parts) if parts else "No changes"
