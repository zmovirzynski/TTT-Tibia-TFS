"""
XML → RevScript converter.

Converts TFS XML registration files (actions.xml, movements.xml, etc.)
into pure Lua RevScript format used by TFS 1.3+.

Handles:
    - actions.xml → Action() RevScripts
    - movements.xml → MoveEvent() RevScripts
    - talkactions.xml → TalkAction() RevScripts
    - creaturescripts.xml → CreatureEvent() RevScripts
    - globalevents.xml → GlobalEvent() RevScripts
"""

import os
import re
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Tuple
from pathlib import Path

from ..utils import read_file_safe, write_file_safe
from ..report import FileReport
from ..mappings.xml_events import (
    ACTION_REGISTRATION,
    MOVEMENT_TYPES,
    MOVEMENT_REGISTRATION,
    TALKACTION_REGISTRATION,
    CREATUREEVENT_TYPES,
    CREATUREEVENT_REGISTRATION,
    GLOBALEVENT_TYPES,
    GLOBALEVENT_REGISTRATION,
)

logger = logging.getLogger("ttt")

class XmlToRevScriptConverter:

    def __init__(self, lua_transformer=None, dry_run: bool = False):
        self.lua_transformer = lua_transformer
        self.dry_run = dry_run
        self.stats = {
            "files_converted": 0,
            "entries_processed": 0,
            "errors": 0,
        }
        self._file_reports: list = []  # List[FileReport] populated per conversion

    def pop_file_reports(self) -> list:
        reports = self._file_reports[:]
        self._file_reports.clear()
        return reports

    def convert_xml_file(self, xml_path: str, scripts_dir: str,
                         output_dir: str) -> List[str]:
        xml_content = read_file_safe(xml_path)
        if not xml_content:
            logger.error(f"Could not read XML file: {xml_path}")
            return []

        filename = os.path.basename(xml_path).lower()

        # Identifica tipo pelo nome (cuidado: talkactions antes de actions)
        if "talkactions" in filename or "talkaction" in filename:
            return self._convert_talkactions(xml_content, scripts_dir, output_dir, xml_path)
        elif "creaturescripts" in filename or "creaturescript" in filename:
            return self._convert_creaturescripts(xml_content, scripts_dir, output_dir, xml_path)
        elif "globalevents" in filename or "globalevent" in filename:
            return self._convert_globalevents(xml_content, scripts_dir, output_dir, xml_path)
        elif "actions" in filename or "action" in filename:
            return self._convert_actions(xml_content, scripts_dir, output_dir, xml_path)
        elif "movements" in filename or "movement" in filename:
            return self._convert_movements(xml_content, scripts_dir, output_dir, xml_path)
        else:
            logger.warning(f"Unknown XML type: {filename}")
            return []

    # Actions

    def _convert_actions(self, xml_content: str, scripts_dir: str,
                         output_dir: str, xml_path: str) -> List[str]:
        output_files = []
        entries = self._parse_xml_entries(xml_content, "action")

        for entry in entries:
            script_name = entry.get("script", "")
            if not script_name:
                continue

            # Read the Lua script
            lua_path = os.path.join(scripts_dir, script_name)
            if not os.path.exists(lua_path):
                lua_path = self._find_script(scripts_dir, script_name)
                if not lua_path:
                    logger.warning(f"Script not found: {script_name}")
                    self.stats["errors"] += 1
                    self._file_reports.append(FileReport(
                        source_path=os.path.join(scripts_dir, script_name),
                        error=f"Script not found: {script_name}", success=False))
                    continue

            lua_code = read_file_safe(lua_path)
            if not lua_code:
                continue

            original_code = lua_code
            fr = FileReport(source_path=lua_path)

            # Transforma o Lua
            if self.lua_transformer:
                lua_code = self.lua_transformer.transform(lua_code, script_name)
                fr.functions_converted = self.lua_transformer.stats.get("functions_converted", 0)
                fr.signatures_updated = self.lua_transformer.stats.get("signatures_updated", 0)
                fr.constants_replaced = self.lua_transformer.stats.get("constants_replaced", 0)
                fr.variables_renamed = self.lua_transformer.stats.get("variables_renamed", 0)
                fr.warnings = list(self.lua_transformer.warnings)

            func_body = self._extract_function_body(lua_code, "onUse")
            if func_body is None:
                func_body = lua_code

            var_name = self._make_var_name(script_name)
            revscript = self._generate_action_revscript(var_name, entry, func_body, lua_code)

            out_name = os.path.splitext(script_name)[0] + ".lua"
            out_name = out_name.replace("/", "_").replace("\\", "_")
            out_path = os.path.join(output_dir, out_name) if output_dir else ""

            if not self.dry_run and out_path:
                write_file_safe(out_path, revscript)
                fr.output_path = out_path
                output_files.append(out_path)

            # Count TTT warnings in generated content
            fr.ttt_warnings = revscript.count("-- TTT:")
            fr.original_content = original_code
            fr.converted_content = revscript

            self._file_reports.append(fr)
            self.stats["files_converted"] += 1
            self.stats["entries_processed"] += 1

        return output_files

    def _generate_action_revscript(self, var_name: str, entry: Dict,
                                    func_body: str, full_code: str) -> str:
        lines = []

        # Add any top-level code (constants, requires, etc.)
        top_code = self._extract_top_level_code(full_code)
        if top_code:
            lines.append(top_code)
            lines.append("")

        lines.append(f"local {var_name} = Action()")
        lines.append("")

        lines.append(f"function {var_name}.onUse(player, item, fromPosition, target, toPosition, isHotkey)")
        lines.append(self._indent_code(func_body))
        lines.append("end")
        lines.append("")

        reg_lines = self._generate_registration_lines(var_name, entry, ACTION_REGISTRATION)
        lines.extend(reg_lines)
        lines.append(f"{var_name}:register()")

        return "\n".join(lines) + "\n"

    def _convert_movements(self, xml_content: str, scripts_dir: str,
                           output_dir: str, xml_path: str) -> List[str]:
        output_files = []
        entries = self._parse_xml_entries(xml_content, "movevent")

        for entry in entries:
            script_name = entry.get("script", "")
            event_type = entry.get("event", entry.get("type", ""))

            if not script_name:
                continue

            lua_path = os.path.join(scripts_dir, script_name)
            if not os.path.exists(lua_path):
                lua_path = self._find_script(scripts_dir, script_name)
                if not lua_path:
                    logger.warning(f"Script not found: {script_name}")
                    self.stats["errors"] += 1
                    self._file_reports.append(FileReport(
                        source_path=os.path.join(scripts_dir, script_name),
                        error=f"Script not found: {script_name}", success=False))
                    continue

            lua_code = read_file_safe(lua_path)
            if not lua_code:
                continue

            original_code = lua_code
            fr = FileReport(source_path=lua_path)

            if self.lua_transformer:
                lua_code = self.lua_transformer.transform(lua_code, script_name)
                fr.functions_converted = self.lua_transformer.stats.get("functions_converted", 0)
                fr.signatures_updated = self.lua_transformer.stats.get("signatures_updated", 0)
                fr.constants_replaced = self.lua_transformer.stats.get("constants_replaced", 0)
                fr.variables_renamed = self.lua_transformer.stats.get("variables_renamed", 0)
                fr.warnings = list(self.lua_transformer.warnings)

            event_method = MOVEMENT_TYPES.get(event_type, f"on{event_type}")

            func_body = self._extract_function_body(lua_code, event_method)
            if func_body is None:
                for old_name in ("onStepIn", "onStepOut", "onEquip", "onDeEquip", "onAddItem"):
                    func_body = self._extract_function_body(lua_code, old_name)
                    if func_body is not None:
                        event_method = old_name
                        break
            if func_body is None:
                func_body = lua_code

            var_name = self._make_var_name(script_name)
            revscript = self._generate_movement_revscript(
                var_name, entry, func_body, lua_code, event_method
            )

            out_name = os.path.splitext(script_name)[0] + ".lua"
            out_name = out_name.replace("/", "_").replace("\\", "_")
            out_path = os.path.join(output_dir, out_name) if output_dir else ""

            if not self.dry_run and out_path:
                write_file_safe(out_path, revscript)
                fr.output_path = out_path
                output_files.append(out_path)

            fr.ttt_warnings = revscript.count("-- TTT:")
            fr.original_content = original_code
            fr.converted_content = revscript
            self._file_reports.append(fr)
            self.stats["files_converted"] += 1
            self.stats["entries_processed"] += 1

        return output_files

    def _generate_movement_revscript(self, var_name: str, entry: Dict,
                                      func_body: str, full_code: str,
                                      event_method: str) -> str:
        lines = []

        top_code = self._extract_top_level_code(full_code)
        if top_code:
            lines.append(top_code)
            lines.append("")

        # Determine signature based on event type
        if event_method in ("onStepIn", "onStepOut"):
            sig = "creature, item, position, fromPosition"
        elif event_method in ("onEquip", "onDeEquip"):
            sig = "player, item, slot, isCheck"
        elif event_method in ("onAddItem", "onRemoveItem"):
            sig = "moveitem, tileitem, position"
        else:
            sig = "creature, item, position, fromPosition"

        lines.append(f"local {var_name} = MoveEvent()")
        lines.append("")
        lines.append(f"function {var_name}.{event_method}({sig})")
        lines.append(self._indent_code(func_body))
        lines.append("end")
        lines.append("")

        event_type = entry.get("event", entry.get("type", ""))
        if event_type:
            lines.append(f'{var_name}:type("{event_type.lower()}")')

        reg_lines = self._generate_registration_lines(var_name, entry, MOVEMENT_REGISTRATION)
        lines.extend(reg_lines)
        lines.append(f"{var_name}:register()")

        return "\n".join(lines) + "\n"

    def _convert_talkactions(self, xml_content: str, scripts_dir: str,
                             output_dir: str, xml_path: str) -> List[str]:
        output_files = []
        entries = self._parse_xml_entries(xml_content, "talkaction")

        for entry in entries:
            script_name = entry.get("script", "")
            words = entry.get("words", "")

            if not script_name:
                continue

            lua_path = os.path.join(scripts_dir, script_name)
            if not os.path.exists(lua_path):
                lua_path = self._find_script(scripts_dir, script_name)
                if not lua_path:
                    logger.warning(f"Script not found: {script_name}")
                    self.stats["errors"] += 1
                    self._file_reports.append(FileReport(
                        source_path=os.path.join(scripts_dir, script_name),
                        error=f"Script not found: {script_name}", success=False))
                    continue

            lua_code = read_file_safe(lua_path)
            if not lua_code:
                continue

            original_code = lua_code
            fr = FileReport(source_path=lua_path)

            if self.lua_transformer:
                lua_code = self.lua_transformer.transform(lua_code, script_name)
                fr.functions_converted = self.lua_transformer.stats.get("functions_converted", 0)
                fr.signatures_updated = self.lua_transformer.stats.get("signatures_updated", 0)
                fr.constants_replaced = self.lua_transformer.stats.get("constants_replaced", 0)
                fr.variables_renamed = self.lua_transformer.stats.get("variables_renamed", 0)
                fr.warnings = list(self.lua_transformer.warnings)

            func_body = self._extract_function_body(lua_code, "onSay")
            if func_body is None:
                func_body = lua_code

            var_name = self._make_var_name(script_name)
            revscript = self._generate_talkaction_revscript(
                var_name, entry, func_body, lua_code, words
            )

            out_name = os.path.splitext(script_name)[0] + ".lua"
            out_name = out_name.replace("/", "_").replace("\\", "_")
            out_path = os.path.join(output_dir, out_name) if output_dir else ""

            if not self.dry_run and out_path:
                write_file_safe(out_path, revscript)
                fr.output_path = out_path
                output_files.append(out_path)

            fr.ttt_warnings = revscript.count("-- TTT:")
            fr.original_content = original_code
            fr.converted_content = revscript
            self._file_reports.append(fr)
            self.stats["files_converted"] += 1
            self.stats["entries_processed"] += 1

        return output_files

    def _generate_talkaction_revscript(self, var_name: str, entry: Dict,
                                        func_body: str, full_code: str,
                                        words: str) -> str:
        lines = []

        top_code = self._extract_top_level_code(full_code)
        if top_code:
            lines.append(top_code)
            lines.append("")

        lines.append(f'local {var_name} = TalkAction("{words}")')
        lines.append("")
        lines.append(f"function {var_name}.onSay(player, words, param)")
        lines.append(self._indent_code(func_body))
        lines.append("end")
        lines.append("")

        separator = entry.get("separator")
        if separator:
            lines.append(f'{var_name}:separator("{separator}")')

        access = entry.get("access")
        if access:
            lines.append(f'{var_name}:access({access})')

        account_type = entry.get("accounttype")
        if account_type:
            lines.append(f'{var_name}:accountType({account_type})')

        lines.append(f"{var_name}:register()")

        return "\n".join(lines) + "\n"

    def _convert_creaturescripts(self, xml_content: str, scripts_dir: str,
                                  output_dir: str, xml_path: str) -> List[str]:
        output_files = []
        entries = self._parse_xml_entries(xml_content, "event")

        for entry in entries:
            script_name = entry.get("script", "")
            event_type = entry.get("type", "").lower()
            event_name = entry.get("name", "")

            if not script_name:
                continue

            lua_path = os.path.join(scripts_dir, script_name)
            if not os.path.exists(lua_path):
                lua_path = self._find_script(scripts_dir, script_name)
                if not lua_path:
                    logger.warning(f"Script not found: {script_name}")
                    self.stats["errors"] += 1
                    self._file_reports.append(FileReport(
                        source_path=os.path.join(scripts_dir, script_name),
                        error=f"Script not found: {script_name}", success=False))
                    continue

            lua_code = read_file_safe(lua_path)
            if not lua_code:
                continue

            original_code = lua_code
            fr = FileReport(source_path=lua_path)

            if self.lua_transformer:
                lua_code = self.lua_transformer.transform(lua_code, script_name)
                fr.functions_converted = self.lua_transformer.stats.get("functions_converted", 0)
                fr.signatures_updated = self.lua_transformer.stats.get("signatures_updated", 0)
                fr.constants_replaced = self.lua_transformer.stats.get("constants_replaced", 0)
                fr.variables_renamed = self.lua_transformer.stats.get("variables_renamed", 0)
                fr.warnings = list(self.lua_transformer.warnings)

            event_method = CREATUREEVENT_TYPES.get(event_type, f"on{event_type.capitalize()}")

            func_body = self._extract_function_body(lua_code, event_method)
            if func_body is None:
                func_body = lua_code

            var_name = self._make_var_name(script_name)
            revscript = self._generate_creaturescript_revscript(
                var_name, entry, func_body, lua_code, event_name, event_type, event_method
            )

            out_name = os.path.splitext(script_name)[0] + ".lua"
            out_name = out_name.replace("/", "_").replace("\\", "_")
            out_path = os.path.join(output_dir, out_name) if output_dir else ""

            if not self.dry_run and out_path:
                write_file_safe(out_path, revscript)
                fr.output_path = out_path
                output_files.append(out_path)

            fr.ttt_warnings = revscript.count("-- TTT:")
            fr.original_content = original_code
            fr.converted_content = revscript
            self._file_reports.append(fr)
            self.stats["files_converted"] += 1
            self.stats["entries_processed"] += 1

        return output_files

    def _generate_creaturescript_revscript(self, var_name: str, entry: Dict,
                                            func_body: str, full_code: str,
                                            event_name: str, event_type: str,
                                            event_method: str) -> str:
        lines = []

        top_code = self._extract_top_level_code(full_code)
        if top_code:
            lines.append(top_code)
            lines.append("")

        lines.append(f'local {var_name} = CreatureEvent("{event_name}")')
        lines.append("")

        sig = self._get_creature_event_signature(event_type)

        lines.append(f"function {var_name}.{event_method}({sig})")
        lines.append(self._indent_code(func_body))
        lines.append("end")
        lines.append("")
        lines.append(f"{var_name}:register()")

        return "\n".join(lines) + "\n"

    def _get_creature_event_signature(self, event_type: str) -> str:
        signatures = {
            "login": "player",
            "logout": "player",
            "death": "creature, corpse, killer, mostDamageKiller, lastHitUnjustified, mostDamageUnjustified",
            "kill": "creature, target",
            "preparedeath": "creature, killer",
            "advance": "player, skill, oldLevel, newLevel",
            "textedit": "player, item, text",
            "healthchange": "creature, attacker, primaryDamage, primaryType, secondaryDamage, secondaryType, origin",
            "manachange": "creature, attacker, primaryDamage, primaryType, secondaryDamage, secondaryType, origin",
            "think": "creature, interval",
            "modalwindow": "player, modalWindowId, buttonId, choiceId",
            "extendedopcode": "player, opcode, buffer",
        }
        return signatures.get(event_type, "creature")

    def _convert_globalevents(self, xml_content: str, scripts_dir: str,
                               output_dir: str, xml_path: str) -> List[str]:
        output_files = []
        entries = self._parse_xml_entries(xml_content, "globalevent")

        for entry in entries:
            script_name = entry.get("script", "")
            event_name = entry.get("name", "")
            event_type = entry.get("type", "").lower()
            interval = entry.get("interval")
            time_val = entry.get("time")

            if not script_name:
                continue

            lua_path = os.path.join(scripts_dir, script_name)
            if not os.path.exists(lua_path):
                lua_path = self._find_script(scripts_dir, script_name)
                if not lua_path:
                    logger.warning(f"Script not found: {script_name}")
                    self.stats["errors"] += 1
                    self._file_reports.append(FileReport(
                        source_path=os.path.join(scripts_dir, script_name),
                        error=f"Script not found: {script_name}", success=False))
                    continue

            lua_code = read_file_safe(lua_path)
            if not lua_code:
                continue

            original_code = lua_code
            fr = FileReport(source_path=lua_path)

            if self.lua_transformer:
                lua_code = self.lua_transformer.transform(lua_code, script_name)
                fr.functions_converted = self.lua_transformer.stats.get("functions_converted", 0)
                fr.signatures_updated = self.lua_transformer.stats.get("signatures_updated", 0)
                fr.constants_replaced = self.lua_transformer.stats.get("constants_replaced", 0)
                fr.variables_renamed = self.lua_transformer.stats.get("variables_renamed", 0)
                fr.warnings = list(self.lua_transformer.warnings)

            if event_type in GLOBALEVENT_TYPES:
                event_method = GLOBALEVENT_TYPES[event_type]
            elif interval:
                event_method = "onThink"
            elif time_val:
                event_method = "onTime"
            else:
                event_method = "onStartup"

            func_body = self._extract_function_body(lua_code, event_method)
            if func_body is None:
                # Try common names
                for name in ("onStartup", "onShutdown", "onRecord", "onThink",
                             "onTime", "onTimer", "onGlobalEvent"):
                    func_body = self._extract_function_body(lua_code, name)
                    if func_body is not None:
                        event_method = name
                        break
            if func_body is None:
                func_body = lua_code

            var_name = self._make_var_name(script_name)
            revscript = self._generate_globalevent_revscript(
                var_name, entry, func_body, lua_code, event_name,
                event_method, interval, time_val
            )

            out_name = os.path.splitext(script_name)[0] + ".lua"
            out_name = out_name.replace("/", "_").replace("\\", "_")
            out_path = os.path.join(output_dir, out_name) if output_dir else ""

            if not self.dry_run and out_path:
                write_file_safe(out_path, revscript)
                fr.output_path = out_path
                output_files.append(out_path)

            fr.ttt_warnings = revscript.count("-- TTT:")
            fr.original_content = original_code
            fr.converted_content = revscript
            self._file_reports.append(fr)
            self.stats["files_converted"] += 1
            self.stats["entries_processed"] += 1

        return output_files
    def _generate_globalevent_revscript(self, var_name: str, entry: Dict,
                                         func_body: str, full_code: str,
                                         event_name: str, event_method: str,
                                         interval: Optional[str],
                                         time_val: Optional[str]) -> str:
        lines = []

        top_code = self._extract_top_level_code(full_code)
        if top_code:
            lines.append(top_code)
            lines.append("")

        lines.append(f'local {var_name} = GlobalEvent("{event_name}")')
        lines.append("")

        if event_method in ("onStartup", "onShutdown"):
            sig = ""
        elif event_method == "onRecord":
            sig = "current, old"
        elif event_method in ("onThink", "onTime", "onTimer"):
            sig = "interval"
        else:
            sig = ""

        lines.append(f"function {var_name}.{event_method}({sig})")
        lines.append(self._indent_code(func_body))
        lines.append("end")
        lines.append("")

        if interval:
            lines.append(f"{var_name}:interval({interval})")
        if time_val:
            lines.append(f'{var_name}:time("{time_val}")')

        lines.append(f"{var_name}:register()")

        return "\n".join(lines) + "\n"

    def _parse_xml_entries(self, xml_content: str, tag_name: str) -> List[Dict]:
        entries = []

        # Clean up XML namespace issues
        xml_content = xml_content.strip()
        if not xml_content:
            return entries

        try:
            root = ET.fromstring(xml_content)
        except ET.ParseError as e:
            # Try wrapping in a root element
            try:
                root = ET.fromstring(f"<root>{xml_content}</root>")
            except ET.ParseError:
                logger.error(f"Failed to parse XML: {e}")
                return entries

        # Find all matching elements
        for elem in root.iter(tag_name):
            entry = dict(elem.attrib)
            entries.append(entry)

        # Also check case-insensitive
        if not entries:
            for elem in root.iter():
                if elem.tag.lower() == tag_name.lower():
                    entry = dict(elem.attrib)
                    entries.append(entry)

        return entries

    def _extract_function_body(self, code: str, func_name: str) -> Optional[str]:
        # Match: function [name.]funcName(...)  or  function funcName(...)
        pattern = re.compile(
            r'function\s+(?:\w+[.:])?'
            + re.escape(func_name)
            + r'[^\S\n]*\([^)]*\)[^\S\n]*\n?',
            re.MULTILINE
        )

        match = pattern.search(code)
        if not match:
            return None

        body_start = match.end()

        # Find matching 'end' - track function/if/for/while/do depth
        depth = 1
        i = body_start
        tokens_pattern = re.compile(
            r'\b(function|if|for|while|do|repeat)\b|\b(end|until)\b',
            re.MULTILINE
        )

        while i < len(code) and depth > 0:
            # Skip strings and comments
            if code[i] == '-' and i + 1 < len(code) and code[i + 1] == '-':
                # Comment
                if i + 2 < len(code) and code[i + 2:i + 4] == '[[':
                    # Long comment
                    end = code.find(']]', i + 4)
                    if end != -1:
                        i = end + 2
                        continue
                # Line comment
                end = code.find('\n', i)
                if end != -1:
                    i = end + 1
                else:
                    break
                continue

            if code[i] in ('"', "'"):
                quote = code[i]
                i += 1
                while i < len(code) and code[i] != quote:
                    if code[i] == '\\':
                        i += 1
                    i += 1
                i += 1
                continue

            if code[i] == '[' and i + 1 < len(code) and code[i + 1] == '[':
                end = code.find(']]', i + 2)
                if end != -1:
                    i = end + 2
                    continue

            # Check for tokens
            token_match = tokens_pattern.match(code, i)
            if token_match:
                # Make sure it's a word boundary
                before_ok = (i == 0 or not (code[i - 1].isalnum() or code[i - 1] == '_'))
                token_end = token_match.end()
                after_ok = (token_end >= len(code) or not (code[token_end].isalnum() or code[token_end] == '_'))

                if before_ok and after_ok:
                    if token_match.group(1):  # Opening keyword
                        depth += 1
                    elif token_match.group(2):  # Closing keyword
                        depth -= 1
                        if depth == 0:
                            body_end = i
                            body = code[body_start:body_end]
                            # Strip leading/trailing blank lines but preserve indentation
                            lines = body.split('\n')
                            # Remove leading empty lines
                            while lines and not lines[0].strip():
                                lines.pop(0)
                            # Remove trailing empty lines
                            while lines and not lines[-1].strip():
                                lines.pop()
                            return '\n'.join(lines)
                    i = token_end
                    continue

            i += 1

        return None

    def _extract_top_level_code(self, code: str) -> str:
        lines = code.split("\n")
        top_lines = []
        in_function = 0

        for line in lines:
            stripped = line.strip()

            # Track function depth
            if re.match(r'\bfunction\b', stripped) and not stripped.startswith("--"):
                in_function += 1
                continue

            if in_function > 0:
                # Count depth-increasing keywords
                if re.search(r'\b(function|if|for|while|do|repeat)\b', stripped) and not stripped.startswith("--"):
                    for m in re.finditer(r'\b(function|if|for|while|do|repeat)\b', stripped):
                        in_function += 1
                if re.search(r'\b(end|until)\b', stripped) and not stripped.startswith("--"):
                    for m in re.finditer(r'\b(end|until)\b', stripped):
                        in_function -= 1
                continue

            # Only include meaningful lines
            if stripped and not stripped.startswith("--") and not stripped == "":
                # Skip the function declarations themselves
                if not stripped.startswith("function"):
                    top_lines.append(line)

        return "\n".join(top_lines).strip()

    def _generate_registration_lines(self, var_name: str, entry: Dict,
                                      reg_info: Dict) -> List[str]:
        lines = []
        id_methods = reg_info.get("id_methods", {})

        # Handle itemid / fromid+toid ranges
        itemid = entry.get("itemid")
        fromid = entry.get("fromid")
        toid = entry.get("toid")
        actionid = entry.get("actionid")
        uniqueid = entry.get("uniqueid")

        if itemid:
            id_method = id_methods.get("itemid", "id")
            # Handle comma-separated IDs
            if ";" in itemid:
                for item_id in itemid.split(";"):
                    item_id = item_id.strip()
                    if item_id:
                        lines.append(f"{var_name}:{id_method}({item_id})")
            else:
                lines.append(f"{var_name}:{id_method}({itemid})")

        if fromid and toid:
            id_method = id_methods.get("fromid", "id")
            lines.append(f"{var_name}:{id_method}({fromid}, {toid})")

        if actionid:
            id_method = id_methods.get("actionid", "aid")
            if ";" in actionid:
                for aid in actionid.split(";"):
                    aid = aid.strip()
                    if aid:
                        lines.append(f"{var_name}:{id_method}({aid})")
            else:
                lines.append(f"{var_name}:{id_method}({actionid})")

        if uniqueid:
            id_method = id_methods.get("uniqueid", "uid")
            lines.append(f"{var_name}:{id_method}({uniqueid})")

        # Handle extra attributes
        extra_attrs = reg_info.get("extra_attrs", {})
        for xml_attr, lua_method in extra_attrs.items():
            val = entry.get(xml_attr)
            if val:
                if val.lower() in ("true", "1", "yes"):
                    lines.append(f"{var_name}:{lua_method}(true)")
                elif val.lower() in ("false", "0", "no"):
                    lines.append(f"{var_name}:{lua_method}(false)")
                else:
                    lines.append(f"{var_name}:{lua_method}({val})")

        return lines

    def _make_var_name(self, script_name: str) -> str:
        # Remove extension and path
        name = os.path.splitext(os.path.basename(script_name))[0]
        # Remove special chars
        name = re.sub(r'[^a-zA-Z0-9_]', '', name)
        # Ensure starts with letter
        if name and name[0].isdigit():
            name = "script_" + name
        if not name:
            name = "script"
        # camelCase
        return name[0].lower() + name[1:] if name else "script"

    def _find_script(self, scripts_dir: str, script_name: str) -> Optional[str]:
        basename = os.path.basename(script_name)
        # Search in scripts_dir and subdirectories
        for root, _, files in os.walk(scripts_dir):
            for f in files:
                if f == basename:
                    return os.path.join(root, f)
        # Also search in parent directory (scripts may be next to XML)
        parent = os.path.dirname(scripts_dir)
        if parent != scripts_dir:
            for root, _, files in os.walk(parent):
                for f in files:
                    if f == basename:
                        return os.path.join(root, f)
        return None

    def _indent_code(self, code: str, indent: str = "\t") -> str:
        lines = code.split("\n")
        # Detect minimum indentation in non-empty lines
        min_indent = float('inf')
        indent_char = " "
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                leading = len(line) - len(stripped)
                min_indent = min(min_indent, leading)
                if line[0:1] == "\t":
                    indent_char = "\t"
        if min_indent == float('inf'):
            min_indent = 0

        # Determine the indent unit (how many chars = 1 indent level)
        indent_unit = 1 if indent_char == "\t" else 4

        indented = []
        for line in lines:
            stripped = line.lstrip()
            if stripped:
                # Remove the common base indentation, then add our indent
                current_leading = len(line) - len(stripped)
                extra = current_leading - min_indent
                # Convert extra spaces to tab-based nesting
                extra_tabs = extra // indent_unit if extra > 0 else 0
                indented.append(indent + ("\t" * extra_tabs) + stripped)
            else:
                indented.append("")
        return "\n".join(indented)

    def get_summary(self) -> str:
        parts = []
        if self.stats["files_converted"]:
            parts.append(f"{self.stats['files_converted']} file(s) converted")
        if self.stats["entries_processed"]:
            parts.append(f"{self.stats['entries_processed']} entry(ies) processed")
        if self.stats["errors"]:
            parts.append(f"{self.stats['errors']} error(s)")
        return ", ".join(parts) if parts else "No conversions"
