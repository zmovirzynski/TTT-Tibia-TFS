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
from typing import Dict, List, Optional

try:
    from luaparser import ast as lua_ast
    LUAPARSER_AVAILABLE = True
except ImportError:
    LUAPARSER_AVAILABLE = False
    lua_ast = None

from ..utils import read_file_safe, write_file_safe
from ..report import FileReport
from ..mappings.xml_events import (
    ACTION_REGISTRATION,
    MOVEMENT_TYPES,
    MOVEMENT_REGISTRATION,
    CREATUREEVENT_TYPES,
    GLOBALEVENT_TYPES,
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

    def _apply_lua_transform(self, lua_code: str, script_name: str, fr: "FileReport") -> str:
        """Apply lua_transformer (if present) and copy stats/warnings into fr."""
        if self.lua_transformer:
            lua_code = self.lua_transformer.transform(lua_code, script_name)
            fr.functions_converted = self.lua_transformer.stats.get("functions_converted", 0)
            fr.signatures_updated = self.lua_transformer.stats.get("signatures_updated", 0)
            fr.constants_replaced = self.lua_transformer.stats.get("constants_replaced", 0)
            fr.variables_renamed = self.lua_transformer.stats.get("variables_renamed", 0)
            fr.warnings = list(self.lua_transformer.warnings)
        return lua_code

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

    def _group_entries_by_script(self, entries: List[Dict]) -> Dict[str, List[Dict]]:
        """Group XML entries by script file name."""
        grouped: Dict[str, List[Dict]] = {}
        for entry in entries:
            script_name = entry.get("script", "")
            if script_name:
                if script_name not in grouped:
                    grouped[script_name] = []
                grouped[script_name].append(entry)
        return grouped

    def _resolve_script_path(self, script_name: str, scripts_dir: str) -> Optional[str]:
        """Resolve the full path to a script file."""
        lua_path = os.path.join(scripts_dir, script_name)
        if os.path.exists(lua_path):
            return lua_path
        return self._find_script(scripts_dir, script_name)

    # Actions

    def _convert_actions(self, xml_content: str, scripts_dir: str,
                         output_dir: str, xml_path: str) -> List[str]:
        output_files = []
        entries = self._parse_xml_entries(xml_content, "action")
        logger.debug(f"  Actions: found {len(entries)} entries in XML")

        # Group entries by script file
        grouped = self._group_entries_by_script(entries)

        for script_name, script_entries in grouped.items():
            lua_path = self._resolve_script_path(script_name, scripts_dir)
            if not lua_path:
                logger.warning(f"Script not found: {script_name}")
                self.stats["errors"] += len(script_entries)
                for entry in script_entries:
                    self._file_reports.append(FileReport(
                        source_path=os.path.join(scripts_dir, script_name),
                        error=f"Script not found: {script_name}", success=False))
                continue

            lua_code = read_file_safe(lua_path)
            if not lua_code:
                continue

            original_code = lua_code
            fr = FileReport(source_path=lua_path)

            # Transform the code once
            lua_code_transformed = self._apply_lua_transform(lua_code, script_name, fr)

            # Generate combined RevScript with all handlers
            var_name = self._make_var_name(script_name)
            revscript = self._generate_combined_action_revscript(
                var_name, script_entries, lua_code, lua_code_transformed
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
            self.stats["entries_processed"] += len(script_entries)

        return output_files
    
    def _generate_combined_action_revscript(self, var_name: str,
                                             entries: List[Dict],
                                             full_code: str,
                                             transformed_code: str) -> str:
        """Generate a combined Action RevScript with multiple registrations."""
        lines = []
        
        # Extract top-level code once
        top_code = self._extract_top_level_code(transformed_code)
        if top_code:
            lines.append(top_code)
            lines.append("")
        
        lines.append(f"local {var_name} = Action()")
        lines.append("")
        lines.append(f"function {var_name}.onUse(player, item, fromPosition, target, toPosition, isHotkey)")
        
        # Extract and transform function body
        func_body = self._extract_function_body(transformed_code, "onUse")
        if func_body is None:
            func_body = "-- TTT: Function body not found"
        
        lines.append(self._indent_code(func_body))
        lines.append("end")
        lines.append("")
        
        # Add all registration lines
        for entry in entries:
            reg_lines = self._generate_registration_lines(var_name, entry, ACTION_REGISTRATION)
            lines.extend(reg_lines)
        
        lines.append(f"{var_name}:register()")
        
        return "\n".join(lines) + "\n"

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
        
        # Group entries by script file
        grouped = self._group_entries_by_script(entries)
        
        for script_name, script_entries in grouped.items():
            lua_path = self._resolve_script_path(script_name, scripts_dir)
            if not lua_path:
                logger.warning(f"Script not found: {script_name}")
                self.stats["errors"] += len(script_entries)
                for entry in script_entries:
                    self._file_reports.append(FileReport(
                        source_path=os.path.join(scripts_dir, script_name),
                        error=f"Script not found: {script_name}", success=False))
                continue
            
            lua_code = read_file_safe(lua_path)
            if not lua_code:
                continue
            
            original_code = lua_code
            fr = FileReport(source_path=lua_path)
            
            # Transform the code once
            lua_code_transformed = self._apply_lua_transform(lua_code, script_name, fr)
            
            # Generate combined RevScript with all handlers
            var_name = self._make_var_name(script_name)
            revscript = self._generate_combined_movement_revscript(
                var_name, script_entries, lua_code, lua_code_transformed
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
            self.stats["entries_processed"] += len(script_entries)
        
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

        event_type = entry.get("type", "")
        if event_type:
            lines.append(f'{var_name}:type("{event_type.lower()}")')

        reg_lines = self._generate_registration_lines(var_name, entry, MOVEMENT_REGISTRATION)
        lines.extend(reg_lines)
        lines.append(f"{var_name}:register()")

        return "\n".join(lines) + "\n"

    def _generate_combined_movement_revscript(self, var_name: str,
                                               entries: List[Dict],
                                               full_code: str,
                                               transformed_code: str) -> str:
        """Generate a combined MoveEvent RevScript with multiple registrations."""
        lines = []
        
        # Extract top-level code once
        top_code = self._extract_top_level_code(transformed_code)
        if top_code:
            lines.append(top_code)
            lines.append("")
        
        lines.append(f"local {var_name} = MoveEvent()")
        lines.append("")
        
        # Determine which handlers we need
        has_step = False
        has_equip = False
        has_additem = False

        for entry in entries:
            event_type = entry.get("type", "")
            event_method = MOVEMENT_TYPES.get(event_type, f"on{event_type}")
            if event_method in ("onStepIn", "onStepOut"):
                has_step = True
            if event_method in ("onEquip", "onDeEquip"):
                has_equip = True
            if event_method in ("onAddItem", "onRemoveItem"):
                has_additem = True

        # Generate onStepIn/onStepOut handler
        if has_step:
            func_body = self._extract_function_body(transformed_code, "onStepIn")
            if func_body is None:
                func_body = self._extract_function_body(transformed_code, "onStepOut")
            if func_body is None:
                func_body = "-- TTT: Function body not found"

            lines.append(f"function {var_name}.onStepIn(creature, item, position, fromPosition)")
            lines.append(self._indent_code(func_body))
            lines.append("end")
            lines.append("")

            lines.append(f"function {var_name}.onStepOut(creature, item, position, fromPosition)")
            lines.append(self._indent_code(func_body))
            lines.append("end")
            lines.append("")

        # Generate onEquip/onDeEquip handler
        if has_equip:
            func_body = self._extract_function_body(transformed_code, "onEquip")
            if func_body is None:
                func_body = self._extract_function_body(transformed_code, "onDeEquip")
            if func_body is None:
                func_body = "-- TTT: Function body not found"

            lines.append(f"function {var_name}.onEquip(player, item, slot, isCheck)")
            lines.append(self._indent_code(func_body))
            lines.append("end")
            lines.append("")

            lines.append(f"function {var_name}.onDeEquip(player, item, slot, isCheck)")
            lines.append(self._indent_code(func_body))
            lines.append("end")
            lines.append("")

        # Generate onAddItem/onRemoveItem handler
        if has_additem:
            func_body = self._extract_function_body(transformed_code, "onAddItem")
            if func_body is None:
                func_body = self._extract_function_body(transformed_code, "onRemoveItem")
            if func_body is None:
                func_body = "-- TTT: Function body not found"

            lines.append(f"function {var_name}.onAddItem(moveitem, tileitem, position)")
            lines.append(self._indent_code(func_body))
            lines.append("end")
            lines.append("")

        # Emit :type() once (all grouped entries share the same type)
        first_type = entries[0].get("type", "") if entries else ""
        if first_type:
            lines.append(f'{var_name}:type("{first_type.lower()}")')

        # Add all registration lines
        for entry in entries:
            reg_lines = self._generate_registration_lines(var_name, entry, MOVEMENT_REGISTRATION)
            lines.extend(reg_lines)

        lines.append(f"{var_name}:register()")
        
        return "\n".join(lines) + "\n"

    def _convert_talkactions(self, xml_content: str, scripts_dir: str,
                             output_dir: str, xml_path: str) -> List[str]:
        output_files = []
        entries = self._parse_xml_entries(xml_content, "talkaction")
        
        # Group entries by script file
        grouped = self._group_entries_by_script(entries)
        
        for script_name, script_entries in grouped.items():
            lua_path = self._resolve_script_path(script_name, scripts_dir)
            if not lua_path:
                logger.warning(f"Script not found: {script_name}")
                self.stats["errors"] += len(script_entries)
                for entry in script_entries:
                    self._file_reports.append(FileReport(
                        source_path=os.path.join(scripts_dir, script_name),
                        error=f"Script not found: {script_name}", success=False))
                continue
            
            lua_code = read_file_safe(lua_path)
            if not lua_code:
                continue
            
            original_code = lua_code
            fr = FileReport(source_path=lua_path)
            
            # Transform the code once
            lua_code_transformed = self._apply_lua_transform(lua_code, script_name, fr)
            
            # Generate combined RevScript
            var_name = self._make_var_name(script_name)
            revscript = self._generate_combined_talkaction_revscript(
                var_name, script_entries, lua_code, lua_code_transformed
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
            self.stats["entries_processed"] += len(script_entries)
        
        return output_files
    
    def _generate_combined_talkaction_revscript(self, var_name: str,
                                                 entries: List[Dict],
                                                 full_code: str,
                                                 transformed_code: str) -> str:
        """Generate a combined TalkAction RevScript with multiple word registrations."""
        lines = []
        
        # Extract top-level code once
        top_code = self._extract_top_level_code(transformed_code)
        if top_code:
            lines.append(top_code)
            lines.append("")
        
        # Collect all words
        all_words = [entry.get("words", "") for entry in entries if entry.get("words")]
        words_str = '", "'.join(all_words)
        
        lines.append(f'local {var_name} = TalkAction("{words_str}")')
        lines.append("")
        
        # Extract function body
        func_body = self._extract_function_body(transformed_code, "onSay")
        if func_body is None:
            func_body = "-- TTT: Function body not found"
        
        lines.append(f"function {var_name}.onSay(player, words, param)")
        lines.append(self._indent_code(func_body))
        lines.append("end")
        lines.append("")
        lines.append(f"{var_name}:register()")
        
        return "\n".join(lines) + "\n"

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
        
        # Group entries by script file
        entries_by_script: Dict[str, List[Dict]] = {}
        for entry in entries:
            script_name = entry.get("script", "")
            if script_name:
                if script_name not in entries_by_script:
                    entries_by_script[script_name] = []
                entries_by_script[script_name].append(entry)
        
        # Process each unique script file once
        for script_name, script_entries in entries_by_script.items():
            lua_path = os.path.join(scripts_dir, script_name)
            if not os.path.exists(lua_path):
                lua_path = self._find_script(scripts_dir, script_name)
                if not lua_path:
                    logger.warning(f"Script not found: {script_name}")
                    self.stats["errors"] += len(script_entries)
                    for entry in script_entries:
                        self._file_reports.append(FileReport(
                            source_path=os.path.join(scripts_dir, script_name),
                            error=f"Script not found: {script_name}", success=False))
                    continue
            
            lua_code = read_file_safe(lua_path)
            if not lua_code:
                continue
            
            original_code = lua_code
            fr = FileReport(source_path=lua_path)
            
            # Transform the Lua code once
            lua_code = self._apply_lua_transform(lua_code, script_name, fr)
            
            # Generate combined RevScript with all handlers
            var_name = self._make_var_name(script_name)
            revscript = self._generate_combined_creaturescript_revscript(
                var_name, script_entries, lua_code, lua_code
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
            self.stats["entries_processed"] += len(script_entries)
        
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

    def _generate_combined_creaturescript_revscript(self, var_name: str, 
                                                     entries: List[Dict],
                                                     full_code: str,
                                                     transformed_code: str) -> str:
        """Generate a combined RevScript with multiple handlers from the same file."""
        lines = []
        
        # Extract top-level code once
        top_code = self._extract_top_level_code(transformed_code)
        if top_code:
            lines.append(top_code)
            lines.append("")
        
        # Use first entry's name for the CreatureEvent
        first_entry = entries[0]
        event_name = first_entry.get("name", var_name.capitalize())
        
        lines.append(f'local {var_name} = CreatureEvent("{event_name}")')
        lines.append("")
        
        # Generate each handler
        for entry in entries:
            event_type = entry.get("type", "").lower()
            event_method = CREATUREEVENT_TYPES.get(event_type, f"on{event_type.capitalize()}")
            
            # Extract function body for this handler
            func_body = self._extract_function_body(transformed_code, event_method)
            if func_body is None:
                func_body = "-- TTT: Function body not found"
            
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
            "traderequest": "creature, target, item",
            "tradeaccept": "creature, target, item, targetItem",
            "moveitem": "creature, item, count, fromPosition, toPosition, fromCylinder, toCylinder",
            "look": "creature, thing, position, distance",
            "spawn": "creature",
            "attack": "creature, target",
            "combat": "creature, target",
        }
        return signatures.get(event_type, "creature")

    def _convert_globalevents(self, xml_content: str, scripts_dir: str,
                               output_dir: str, xml_path: str) -> List[str]:
        output_files = []
        entries = self._parse_xml_entries(xml_content, "globalevent")
        
        # Group entries by script file
        grouped = self._group_entries_by_script(entries)
        
        for script_name, script_entries in grouped.items():
            lua_path = self._resolve_script_path(script_name, scripts_dir)
            if not lua_path:
                logger.warning(f"Script not found: {script_name}")
                self.stats["errors"] += len(script_entries)
                for entry in script_entries:
                    self._file_reports.append(FileReport(
                        source_path=os.path.join(scripts_dir, script_name),
                        error=f"Script not found: {script_name}", success=False))
                continue
            
            lua_code = read_file_safe(lua_path)
            if not lua_code:
                continue
            
            original_code = lua_code
            fr = FileReport(source_path=lua_path)
            
            # Transform the code once
            lua_code_transformed = self._apply_lua_transform(lua_code, script_name, fr)
            
            # Generate combined RevScript
            var_name = self._make_var_name(script_name)
            revscript = self._generate_combined_globalevent_revscript(
                var_name, script_entries, lua_code, lua_code_transformed
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
            self.stats["entries_processed"] += len(script_entries)
        
        return output_files
    
    def _generate_combined_globalevent_revscript(self, var_name: str,
                                                  entries: List[Dict],
                                                  full_code: str,
                                                  transformed_code: str) -> str:
        """Generate a combined GlobalEvent RevScript with multiple handlers."""
        lines = []
        
        # Extract top-level code once
        top_code = self._extract_top_level_code(transformed_code)
        if top_code:
            lines.append(top_code)
            lines.append("")
        
        # Use first entry's name
        first_entry = entries[0]
        event_name = first_entry.get("name", var_name.capitalize())
        
        lines.append(f'local {var_name} = GlobalEvent("{event_name}")')
        lines.append("")
        
        # Generate each handler
        for entry in entries:
            event_type = entry.get("type", "").lower()
            interval = entry.get("interval")
            time_val = entry.get("time")
            
            # Determine event method
            if event_type in GLOBALEVENT_TYPES:
                event_method = GLOBALEVENT_TYPES[event_type]
            elif interval:
                event_method = "onThink"
            elif time_val:
                event_method = "onTime"
            else:
                event_method = "onStartup"
            
            # Try to extract function body
            func_body = self._extract_function_body(transformed_code, event_method)
            if func_body is None:
                # Try common names
                for name in ("onStartup", "onShutdown", "onRecord", "onThink",
                            "onTime", "onTimer", "onGlobalEvent"):
                    func_body = self._extract_function_body(transformed_code, name)
                    if func_body is not None:
                        break
            if func_body is None:
                func_body = "-- TTT: Function body not found"
            
            # Determine signature
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
            
            # Add interval/time if specified
            if interval:
                lines.append(f"{var_name}:interval({interval})")
            if time_val:
                lines.append(f'{var_name}:time("{time_val}")')
        
        lines.append(f"{var_name}:register()")
        
        return "\n".join(lines) + "\n"
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
            
            # Normalize alternative formats:
            # Format: event="script" value="nome.lua" -> script="nome.lua"
            if entry.get("event") == "script" and "value" in entry and "script" not in entry:
                entry["script"] = entry["value"]
            
            # Format: event="function" value="onUse" -> method="onUse"
            if entry.get("event") == "function" and "value" in entry:
                entry["method"] = entry["value"]
            
            entries.append(entry)

        # Also check case-insensitive
        if not entries:
            for elem in root.iter():
                if elem.tag.lower() == tag_name.lower():
                    entry = dict(elem.attrib)
                    
                    # Normalize alternative formats (same as above)
                    if entry.get("event") == "script" and "value" in entry and "script" not in entry:
                        entry["script"] = entry["value"]
                    if entry.get("event") == "function" and "value" in entry:
                        entry["method"] = entry["value"]
                    
                    entries.append(entry)

        return entries

    def _extract_function_body(self, code: str, func_name: str) -> Optional[str]:
        """Extract the body of a named function using AST with regex fallback."""
        if not LUAPARSER_AVAILABLE:
            return self._extract_function_body_regex(code, func_name)

        try:
            tree = lua_ast.parse(code)
            for node in lua_ast.walk(tree):
                if not isinstance(node, lua_ast.Function):
                    continue
                if self._get_function_name(node) != func_name:
                    continue

                body_block = getattr(node, 'body', None)
                if body_block and hasattr(body_block, 'body') and body_block.body:
                    last_stmt = body_block.body[-1]
                    last_char = getattr(last_stmt, 'stop_char', None)
                    func_start = getattr(node, 'start_char', None)
                    if func_start is not None and last_char is not None:
                        first_nl = code.find('\n', func_start)
                        if first_nl != -1:
                            return code[first_nl + 1:last_char + 1]

                # Body positions unavailable — use function-level offsets and strip the wrapper
                start_char = getattr(node, 'start_char', None)
                stop_char = getattr(node, 'stop_char', None)
                if start_char is not None and stop_char is not None:
                    func_block = code[start_char:stop_char]
                    first_nl = func_block.find('\n')
                    if first_nl != -1:
                        body = func_block[first_nl + 1:].rstrip()
                        if body.endswith('end'):
                            body = body[:-3].rstrip()
                        return body

        except Exception as e:
            logger.warning(f"AST extraction failed for {func_name}: {e}")

        return None
    
    def _extract_function_body_regex(self, code: str, func_name: str) -> Optional[str]:
        """Regex fallback for extracting a function body when luaparser is unavailable."""
        import re
        pattern = re.compile(
            r'^[ \t]*(?:local\s+)?function\s+' + re.escape(func_name) + r'\s*\([^)]*\)\s*\n(.*?)\nend\s*$',
            re.MULTILINE | re.DOTALL,
        )
        m = pattern.search(code)
        if m:
            return m.group(1)
        return None

    def _get_function_name(self, node) -> Optional[str]:
        """Extract function name from AST node."""
        if not isinstance(node, lua_ast.Function):
            return None
        
        # Handle local function name or function name()
        if hasattr(node, 'name') and node.name:
            if isinstance(node.name, lua_ast.Name):
                return node.name.id
            elif isinstance(node.name, str):
                return node.name
        
        # Handle method calls like function obj:method()
        if hasattr(node, 'value') and hasattr(node.value, 'name'):
            if isinstance(node.value.name, str):
                return node.value.name
        
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

        def parse_id_range(id_str: str) -> List[str]:
            """Parse ID string that may contain ranges (e.g., '13919-13930' or '100;200').
            Returns list of registration line arguments."""
            result = []
            id_str = id_str.strip()
            
            # Handle semicolon-separated values
            if ";" in id_str:
                for part in id_str.split(";"):
                    part = part.strip()
                    if part:
                        result.extend(parse_id_range(part))
                return result
            
            # Handle range with hyphen (e.g., '13919-13930')
            if "-" in id_str:
                parts = id_str.split("-")
                if len(parts) == 2:
                    from_val = parts[0].strip()
                    to_val = parts[1].strip()
                    return [f"{from_val}, {to_val}"]
            
            # Single ID
            return [id_str]

        if itemid:
            id_method = id_methods.get("itemid", "id")
            for id_arg in parse_id_range(itemid):
                lines.append(f"{var_name}:{id_method}({id_arg})")

        if fromid and toid:
            id_method = id_methods.get("fromid", "id")
            lines.append(f"{var_name}:{id_method}({fromid}, {toid})")

        if actionid:
            id_method = id_methods.get("actionid", "aid")
            for id_arg in parse_id_range(actionid):
                lines.append(f"{var_name}:{id_method}({id_arg})")

        if uniqueid:
            id_method = id_methods.get("uniqueid", "uid")
            for id_arg in parse_id_range(uniqueid):
                lines.append(f"{var_name}:{id_method}({id_arg})")

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
