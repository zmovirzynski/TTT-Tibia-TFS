"""
Folder scanner - Detects the structure and script types in a TFS data folder.
"""

import os
import logging
from typing import List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("ttt")


@dataclass
class ScanResult:
    root_dir: str
    lua_files: List[str] = field(default_factory=list)
    xml_files: List[str] = field(default_factory=list)

    # Detected XML registration files
    actions_xml: Optional[str] = None
    movements_xml: Optional[str] = None
    talkactions_xml: Optional[str] = None
    creaturescripts_xml: Optional[str] = None
    globalevents_xml: Optional[str] = None

    # Script directories
    actions_dir: Optional[str] = None
    movements_dir: Optional[str] = None
    talkactions_dir: Optional[str] = None
    creaturescripts_dir: Optional[str] = None
    globalevents_dir: Optional[str] = None

    # NPC directories
    npc_dir: Optional[str] = None
    npc_scripts_dir: Optional[str] = None
    npc_xml_files: List[str] = field(default_factory=list)

    # RevScript directories (if present)
    scripts_dir: Optional[str] = None

    # Detected TFS version hints
    version_hints: List[str] = field(default_factory=list)

    def summary(self) -> str:
        lines = [f"Scan results for: {self.root_dir}"]
        lines.append(f"  Lua files: {len(self.lua_files)}")
        lines.append(f"  XML files: {len(self.xml_files)}")

        if self.actions_xml:
            lines.append(f"  Actions XML: {os.path.basename(self.actions_xml)}")
            if self.actions_dir:
                count = self._count_lua(self.actions_dir)
                lines.append(f"    Scripts dir: {self.actions_dir} ({count} lua files)")

        if self.movements_xml:
            lines.append(f"  Movements XML: {os.path.basename(self.movements_xml)}")
            if self.movements_dir:
                count = self._count_lua(self.movements_dir)
                lines.append(f"    Scripts dir: {self.movements_dir} ({count} lua files)")

        if self.talkactions_xml:
            lines.append(f"  TalkActions XML: {os.path.basename(self.talkactions_xml)}")
            if self.talkactions_dir:
                count = self._count_lua(self.talkactions_dir)
                lines.append(f"    Scripts dir: {self.talkactions_dir} ({count} lua files)")

        if self.creaturescripts_xml:
            lines.append(f"  CreatureScripts XML: {os.path.basename(self.creaturescripts_xml)}")
            if self.creaturescripts_dir:
                count = self._count_lua(self.creaturescripts_dir)
                lines.append(f"    Scripts dir: {self.creaturescripts_dir} ({count} lua files)")

        if self.globalevents_xml:
            lines.append(f"  GlobalEvents XML: {os.path.basename(self.globalevents_xml)}")
            if self.globalevents_dir:
                count = self._count_lua(self.globalevents_dir)
                lines.append(f"    Scripts dir: {self.globalevents_dir} ({count} lua files)")

        if self.npc_dir:
            lines.append(f"  NPC dir: {self.npc_dir}")
            if self.npc_scripts_dir:
                count = self._count_lua(self.npc_scripts_dir)
                lines.append(f"    Scripts dir: {self.npc_scripts_dir} ({count} lua files)")
            lines.append(f"    NPC XML files: {len(self.npc_xml_files)}")

        if self.scripts_dir:
            lines.append(f"  RevScript dir detected: {self.scripts_dir}")

        if self.version_hints:
            lines.append(f"  Version hints: {', '.join(self.version_hints)}")

        return "\n".join(lines)

    def _count_lua(self, directory: str) -> int:
        count = 0
        for _, _, files in os.walk(directory):
            count += sum(1 for f in files if f.endswith(".lua"))
        return count


def scan_directory(root_dir: str) -> ScanResult:
    """Varre o diretório e detecta a estrutura do TFS (XMLs, Lua, NPC, etc.)."""
    result = ScanResult(root_dir=root_dir)

    if not os.path.isdir(root_dir):
        logger.error(f"Directory does not exist: {root_dir}")
        return result

    for root, dirs, files in os.walk(root_dir):
        for f in files:
            full = os.path.join(root, f)
            if f.endswith(".lua"):
                result.lua_files.append(full)
            elif f.endswith(".xml"):
                result.xml_files.append(full)

    # XML / scripts por componente
    _detect_component(result, root_dir, "actions",
                      ["actions.xml"],
                      ["scripts", "lib"],
                      "actions_xml", "actions_dir")

    _detect_component(result, root_dir, "movements",
                      ["movements.xml"],
                      ["scripts", "lib"],
                      "movements_xml", "movements_dir")

    _detect_component(result, root_dir, "talkactions",
                      ["talkactions.xml"],
                      ["scripts", "lib"],
                      "talkactions_xml", "talkactions_dir")

    _detect_component(result, root_dir, "creaturescripts",
                      ["creaturescripts.xml"],
                      ["scripts", "lib"],
                      "creaturescripts_xml", "creaturescripts_dir")

    _detect_component(result, root_dir, "globalevents",
                      ["globalevents.xml"],
                      ["scripts", "lib"],
                      "globalevents_xml", "globalevents_dir")

    _detect_npc_component(result, root_dir)

    for name in ("scripts", "data/scripts", "revscripts"):
        scripts_path = os.path.join(root_dir, name)
        if os.path.isdir(scripts_path):
            result.scripts_dir = scripts_path
            break

    result.version_hints = _detect_version(result)

    return result


def _detect_component(result: ScanResult, root_dir: str,
                       component_name: str,
                       xml_names: List[str],
                       script_subdirs: List[str],
                       xml_attr: str, dir_attr: str):

    search_paths = [
        os.path.join(root_dir, component_name),
        os.path.join(root_dir, "data", component_name),
        os.path.join(root_dir, "data", "scripts", component_name),
    ]

    for base_path in search_paths:
        if not os.path.isdir(base_path):
            continue

        for xml_name in xml_names:
            xml_path = os.path.join(base_path, xml_name)
            if os.path.isfile(xml_path):
                setattr(result, xml_attr, xml_path)
                break

        for subdir in script_subdirs:
            scripts_path = os.path.join(base_path, subdir)
            if os.path.isdir(scripts_path):
                setattr(result, dir_attr, scripts_path)
                break

        if getattr(result, dir_attr) is None:
            lua_count = sum(1 for f in os.listdir(base_path) if f.endswith(".lua"))
            if lua_count > 0:
                setattr(result, dir_attr, base_path)

        if getattr(result, xml_attr) is not None:
            break

    if getattr(result, xml_attr) is None:
        for xml_file in result.xml_files:
            basename = os.path.basename(xml_file).lower()
            if basename in [n.lower() for n in xml_names]:
                setattr(result, xml_attr, xml_file)
                # Set script dir to same directory
                if getattr(result, dir_attr) is None:
                    parent = os.path.dirname(xml_file)
                    scripts_path = os.path.join(parent, "scripts")
                    if os.path.isdir(scripts_path):
                        setattr(result, dir_attr, scripts_path)
                    else:
                        setattr(result, dir_attr, parent)
                break


def _detect_npc_component(result: ScanResult, root_dir: str):
    search_paths = [
        os.path.join(root_dir, "npc"),
        os.path.join(root_dir, "npcs"),
        os.path.join(root_dir, "data", "npc"),
        os.path.join(root_dir, "data", "npcs"),
    ]

    for npc_path in search_paths:
        if not os.path.isdir(npc_path):
            continue

        result.npc_dir = npc_path

        for f in os.listdir(npc_path):
            if f.lower().endswith(".xml"):
                result.npc_xml_files.append(os.path.join(npc_path, f))

        for subdir in ("scripts", "lib"):
            scripts_path = os.path.join(npc_path, subdir)
            if os.path.isdir(scripts_path):
                result.npc_scripts_dir = scripts_path
                break

        if result.npc_scripts_dir is None:
            lua_count = sum(1 for f in os.listdir(npc_path) if f.endswith(".lua"))
            if lua_count > 0:
                result.npc_scripts_dir = npc_path

        break  # Found a valid NPC dir


def _detect_version(result: ScanResult) -> List[str]:
    hints = []
    sample_files = result.lua_files[:20]  # Check first 20 files

    has_old_api = False
    has_new_api = False
    has_revscript = False

    for filepath in sample_files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(4096)  # Read first 4KB
        except (IOError, OSError):
            continue

        # API antiga (0.3/0.4)
        if any(p in content for p in [
            "doPlayerSendTextMessage", "doPlayerAddItem", "getCreatureName",
            "getPlayerLevel", "doTeleportThing", "getPlayerStorageValue",
            "doPlayerSendCancel", "doCreatureAddHealth"
        ]):
            has_old_api = True

        # API nova (1.x)
        if any(p in content for p in [
            "player:sendTextMessage", "player:addItem", "player:getLevel",
            "creature:getHealth", "player:getStorageValue",
        ]):
            has_new_api = True

        # RevScript
        if any(p in content for p in [
            "Action()", "MoveEvent()", "TalkAction(",
            "CreatureEvent(", "GlobalEvent(",
            ":register()"
        ]):
            has_revscript = True

    if has_old_api and not has_new_api:
        hints.append("TFS 0.3/0.4 (old procedural API detected)")
    elif has_old_api and has_new_api:
        hints.append("Mixed API (partially converted?)")
    elif has_new_api and not has_revscript:
        hints.append("TFS 1.x (OOP API, XML registration)")
    elif has_new_api and has_revscript:
        hints.append("TFS 1.3+ (RevScript)")

    return hints
