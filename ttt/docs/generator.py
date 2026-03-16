"""
Docs generator — Scans an OTServ data folder and extracts documentation entries.

Supports:
  - Actions (item ID, script, description)
  - TalkActions (keyword, script)
  - Movements (item/tile, type, script)
  - CreatureScripts (event, script)
  - GlobalEvents (type, interval, script)
  - NPCs (name, position, keywords)
  - Spells (name, mana, level, formula)
"""

import os
import re
import logging
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from ..utils import find_xml_files, find_lua_files, read_file_safe

logger = logging.getLogger("ttt")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DocEntry:
    """A single documentation entry."""
    category: str  # actions, movements, talkactions, creaturescripts, globalevents, npcs, spells
    name: str
    script: str = ""
    description: str = ""
    attributes: Dict[str, str] = field(default_factory=dict)
    source_file: str = ""
    lua_content: str = ""

    def as_dict(self) -> Dict:
        d = {
            "category": self.category,
            "name": self.name,
            "script": self.script,
            "description": self.description,
        }
        if self.attributes:
            d["attributes"] = dict(self.attributes)
        if self.source_file:
            d["source_file"] = self.source_file
        return d


@dataclass
class DocsReport:
    """Complete documentation report for a server."""
    directory: str = ""
    actions: List[DocEntry] = field(default_factory=list)
    movements: List[DocEntry] = field(default_factory=list)
    talkactions: List[DocEntry] = field(default_factory=list)
    creaturescripts: List[DocEntry] = field(default_factory=list)
    globalevents: List[DocEntry] = field(default_factory=list)
    npcs: List[DocEntry] = field(default_factory=list)
    spells: List[DocEntry] = field(default_factory=list)

    @property
    def total_entries(self) -> int:
        return (len(self.actions) + len(self.movements) +
                len(self.talkactions) + len(self.creaturescripts) +
                len(self.globalevents) + len(self.npcs) + len(self.spells))

    @property
    def categories(self) -> Dict[str, List[DocEntry]]:
        return {
            "actions": self.actions,
            "movements": self.movements,
            "talkactions": self.talkactions,
            "creaturescripts": self.creaturescripts,
            "globalevents": self.globalevents,
            "npcs": self.npcs,
            "spells": self.spells,
        }

    def as_dict(self) -> Dict:
        return {
            "directory": self.directory,
            "total_entries": self.total_entries,
            "actions": [e.as_dict() for e in self.actions],
            "movements": [e.as_dict() for e in self.movements],
            "talkactions": [e.as_dict() for e in self.talkactions],
            "creaturescripts": [e.as_dict() for e in self.creaturescripts],
            "globalevents": [e.as_dict() for e in self.globalevents],
            "npcs": [e.as_dict() for e in self.npcs],
            "spells": [e.as_dict() for e in self.spells],
        }


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------

class DocsGenerator:
    """Scans a server directory and builds DocsReport."""

    def generate(self, directory: str) -> DocsReport:
        """Scan the given directory and produce a documentation report."""
        report = DocsReport(directory=directory)

        if not os.path.isdir(directory):
            logger.error(f"Directory not found: {directory}")
            return report

        xml_files = find_xml_files(directory)

        for xml_path in xml_files:
            basename = os.path.basename(xml_path).lower()
            if basename == "actions.xml":
                report.actions.extend(self._parse_actions(xml_path))
            elif basename == "movements.xml":
                report.movements.extend(self._parse_movements(xml_path))
            elif basename == "talkactions.xml":
                report.talkactions.extend(self._parse_talkactions(xml_path))
            elif basename == "creaturescripts.xml":
                report.creaturescripts.extend(self._parse_creaturescripts(xml_path))
            elif basename == "globalevents.xml":
                report.globalevents.extend(self._parse_globalevents(xml_path))
            elif basename == "spells.xml":
                report.spells.extend(self._parse_spells(xml_path))

        # Parse NPC XML files (any XML with <npc> root)
        for xml_path in xml_files:
            basename = os.path.basename(xml_path).lower()
            # Skip registration XMLs
            if basename in ("actions.xml", "movements.xml", "talkactions.xml",
                            "creaturescripts.xml", "globalevents.xml", "spells.xml"):
                continue
            npc_entry = self._parse_npc_xml(xml_path)
            if npc_entry:
                report.npcs.append(npc_entry)

        # Also scan for RevScript-style registrations in Lua files
        lua_files = find_lua_files(directory)
        for lua_path in lua_files:
            entries = self._parse_revscript_lua(lua_path)
            for entry in entries:
                cat = entry.category
                getattr(report, cat).append(entry)

        return report

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _parse_actions(self, xml_path: str) -> List[DocEntry]:
        entries = []
        tree = self._safe_parse_xml(xml_path)
        if tree is None:
            return entries

        root = tree.getroot()
        xml_dir = os.path.dirname(xml_path)

        for elem in root.iter("action"):
            attribs = dict(elem.attrib)
            script = attribs.pop("script", "")
            # Build name from IDs
            ids = []
            for id_attr in ("itemid", "fromid", "actionid", "uniqueid"):
                val = attribs.get(id_attr)
                if val:
                    ids.append(f"{id_attr}={val}")
            name = script.replace(".lua", "") if script else ", ".join(ids) or "action"
            desc = self._extract_description(xml_dir, script)

            entry = DocEntry(
                category="actions",
                name=name,
                script=script,
                description=desc,
                attributes=attribs,
                source_file=xml_path,
            )
            entry.lua_content = self._read_script(xml_dir, script)
            entries.append(entry)

        return entries

    # ------------------------------------------------------------------
    # Movements
    # ------------------------------------------------------------------

    def _parse_movements(self, xml_path: str) -> List[DocEntry]:
        entries = []
        tree = self._safe_parse_xml(xml_path)
        if tree is None:
            return entries

        root = tree.getroot()
        xml_dir = os.path.dirname(xml_path)

        for elem in root.iter("movevent"):
            attribs = dict(elem.attrib)
            script = attribs.pop("script", "")
            event_type = attribs.get("type", "")
            # Build name
            ids = []
            for id_attr in ("itemid", "fromid", "actionid", "uniqueid", "tileitem"):
                val = attribs.get(id_attr)
                if val:
                    ids.append(f"{id_attr}={val}")
            id_str = ", ".join(ids)
            name = script.replace(".lua", "") if script else event_type or "movement"
            desc = self._extract_description(xml_dir, script)

            entry = DocEntry(
                category="movements",
                name=name,
                script=script,
                description=desc,
                attributes=attribs,
                source_file=xml_path,
            )
            entry.lua_content = self._read_script(xml_dir, script)
            entries.append(entry)

        return entries

    # ------------------------------------------------------------------
    # TalkActions
    # ------------------------------------------------------------------

    def _parse_talkactions(self, xml_path: str) -> List[DocEntry]:
        entries = []
        tree = self._safe_parse_xml(xml_path)
        if tree is None:
            return entries

        root = tree.getroot()
        xml_dir = os.path.dirname(xml_path)

        for elem in root.iter("talkaction"):
            attribs = dict(elem.attrib)
            script = attribs.pop("script", "")
            words = attribs.get("words", "")
            name = words if words else (script.replace(".lua", "") if script else "talkaction")
            desc = self._extract_description(xml_dir, script)

            entry = DocEntry(
                category="talkactions",
                name=name,
                script=script,
                description=desc,
                attributes=attribs,
                source_file=xml_path,
            )
            entry.lua_content = self._read_script(xml_dir, script)
            entries.append(entry)

        return entries

    # ------------------------------------------------------------------
    # CreatureScripts
    # ------------------------------------------------------------------

    def _parse_creaturescripts(self, xml_path: str) -> List[DocEntry]:
        entries = []
        tree = self._safe_parse_xml(xml_path)
        if tree is None:
            return entries

        root = tree.getroot()
        xml_dir = os.path.dirname(xml_path)

        for elem in root.iter("event"):
            attribs = dict(elem.attrib)
            script = attribs.pop("script", "")
            event_name = attribs.get("name", "")
            event_type = attribs.get("type", "")
            name = event_name if event_name else event_type or (script.replace(".lua", "") if script else "event")
            desc = self._extract_description(xml_dir, script)

            entry = DocEntry(
                category="creaturescripts",
                name=name,
                script=script,
                description=desc,
                attributes=attribs,
                source_file=xml_path,
            )
            entry.lua_content = self._read_script(xml_dir, script)
            entries.append(entry)

        return entries

    # ------------------------------------------------------------------
    # GlobalEvents
    # ------------------------------------------------------------------

    def _parse_globalevents(self, xml_path: str) -> List[DocEntry]:
        entries = []
        tree = self._safe_parse_xml(xml_path)
        if tree is None:
            return entries

        root = tree.getroot()
        xml_dir = os.path.dirname(xml_path)

        for elem in root.iter("globalevent"):
            attribs = dict(elem.attrib)
            script = attribs.pop("script", "")
            event_name = attribs.get("name", "")
            event_type = attribs.get("type", "")
            interval = attribs.get("interval", "")
            name = event_name if event_name else (script.replace(".lua", "") if script else "globalevent")
            desc = self._extract_description(xml_dir, script)

            entry = DocEntry(
                category="globalevents",
                name=name,
                script=script,
                description=desc,
                attributes=attribs,
                source_file=xml_path,
            )
            entry.lua_content = self._read_script(xml_dir, script)
            entries.append(entry)

        return entries

    # ------------------------------------------------------------------
    # Spells
    # ------------------------------------------------------------------

    def _parse_spells(self, xml_path: str) -> List[DocEntry]:
        entries = []
        tree = self._safe_parse_xml(xml_path)
        if tree is None:
            return entries

        root = tree.getroot()
        xml_dir = os.path.dirname(xml_path)

        for tag in ("instant", "rune"):
            for elem in root.iter(tag):
                attribs = dict(elem.attrib)
                script = attribs.pop("script", "")
                spell_name = attribs.get("name", "")
                mana = attribs.get("mana", "")
                level = attribs.get("lvl", attribs.get("level", ""))
                name = spell_name if spell_name else (script.replace(".lua", "") if script else tag)
                desc = self._extract_description(xml_dir, script)

                entry = DocEntry(
                    category="spells",
                    name=name,
                    script=script,
                    description=desc,
                    attributes=attribs,
                    source_file=xml_path,
                )
                entry.lua_content = self._read_script(xml_dir, script)
                entries.append(entry)

        return entries

    # ------------------------------------------------------------------
    # NPCs
    # ------------------------------------------------------------------

    def _parse_npc_xml(self, xml_path: str) -> Optional[DocEntry]:
        """Parse a single NPC XML file (<npc> root element)."""
        tree = self._safe_parse_xml(xml_path)
        if tree is None:
            return None

        root = tree.getroot()
        if root.tag.lower() != "npc":
            return None

        attribs = dict(root.attrib)
        npc_name = attribs.get("name", os.path.basename(xml_path).replace(".xml", ""))
        script = attribs.get("script", "")
        xml_dir = os.path.dirname(xml_path)

        # Extract look
        look_elem = root.find("look")
        look_info = dict(look_elem.attrib) if look_elem is not None else {}

        # Extract health
        health_elem = root.find("health")
        health_info = dict(health_elem.attrib) if health_elem is not None else {}

        # Extract parameters
        params = {}
        for param_elem in root.iter("parameter"):
            key = param_elem.get("key", "")
            value = param_elem.get("value", "")
            if key:
                params[key] = value

        # Extract keywords from NPC script
        keywords = []
        lua_content = ""
        if script:
            lua_content = self._read_script(xml_dir, script)
            if not lua_content:
                # Try scripts/ subdir
                lua_content = self._read_script(xml_dir, os.path.join("scripts", script))
            if lua_content:
                keywords = self._extract_npc_keywords(lua_content)

        # Build attributes
        entry_attrs = {}
        if look_info:
            entry_attrs["look_type"] = look_info.get("type", "")
        if health_info:
            entry_attrs["health"] = health_info.get("max", health_info.get("now", ""))
        if params.get("message_greet"):
            entry_attrs["greet"] = params["message_greet"]
        if keywords:
            entry_attrs["keywords"] = ", ".join(keywords)
        if params.get("shop_buyable"):
            entry_attrs["shop_buyable"] = params["shop_buyable"]
        if params.get("shop_sellable"):
            entry_attrs["shop_sellable"] = params["shop_sellable"]

        # Description from greet message or first comment in script
        desc = params.get("message_greet", "")
        if not desc and lua_content:
            desc = self._extract_description_from_content(lua_content)

        entry = DocEntry(
            category="npcs",
            name=npc_name,
            script=script,
            description=desc,
            attributes=entry_attrs,
            source_file=xml_path,
        )
        entry.lua_content = lua_content

        return entry

    # ------------------------------------------------------------------
    # RevScript Lua detection
    # ------------------------------------------------------------------

    def _parse_revscript_lua(self, lua_path: str) -> List[DocEntry]:
        """Detect RevScript-style registrations in a Lua file."""
        entries = []
        content = read_file_safe(lua_path)
        if not content:
            return entries

        # Only process RevScript files (must have :register())
        if ":register()" not in content:
            return entries

        # Detect registration type
        patterns = [
            (r'local\s+(\w+)\s*=\s*Action\s*\(\s*\)', "actions"),
            (r'local\s+(\w+)\s*=\s*MoveEvent\s*\(\s*\)', "movements"),
            (r'local\s+(\w+)\s*=\s*TalkAction\s*\(\s*["\'](.+?)["\']\s*\)', "talkactions"),
            (r'local\s+(\w+)\s*=\s*CreatureEvent\s*\(\s*["\'](.+?)["\']\s*\)', "creaturescripts"),
            (r'local\s+(\w+)\s*=\s*GlobalEvent\s*\(\s*["\'](.+?)["\']\s*\)', "globalevents"),
        ]

        desc = self._extract_description_from_content(content)
        basename = os.path.basename(lua_path)
        name = basename.replace(".lua", "")

        for pattern, category in patterns:
            m = re.search(pattern, content)
            if m:
                attribs = {}
                # Extract IDs for actions/movements
                for id_pat in [r':id\s*\(\s*(\d+)\s*\)', r':aid\s*\(\s*(\d+)\s*\)',
                               r':uid\s*\(\s*(\d+)\s*\)']:
                    id_m = re.findall(id_pat, content)
                    if id_m:
                        id_name = "id" if ":id(" in id_pat else ("aid" if ":aid(" in id_pat else "uid")
                        attribs[id_name] = ", ".join(id_m)

                if category == "talkactions" and m.lastindex and m.lastindex >= 2:
                    name = m.group(2)
                    attribs["words"] = m.group(2)
                elif category in ("creaturescripts", "globalevents") and m.lastindex and m.lastindex >= 2:
                    name = m.group(2)

                entry = DocEntry(
                    category=category,
                    name=name,
                    script=basename,
                    description=desc,
                    attributes=attribs,
                    source_file=lua_path,
                )
                entry.lua_content = content
                entries.append(entry)

        return entries

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _safe_parse_xml(self, xml_path: str) -> Optional[ET.ElementTree]:
        """Parse XML, returning None on error."""
        try:
            content = read_file_safe(xml_path)
            if not content:
                return None
            return ET.ElementTree(ET.fromstring(content))
        except ET.ParseError:
            logger.debug(f"XML parse error: {xml_path}")
            return None

    def _read_script(self, xml_dir: str, script_name: str) -> str:
        """Try to read the Lua script referenced by an XML entry."""
        if not script_name:
            return ""
        # Try direct path
        path = os.path.join(xml_dir, script_name)
        if os.path.isfile(path):
            return read_file_safe(path) or ""
        # Try scripts/ subdir
        path = os.path.join(xml_dir, "scripts", script_name)
        if os.path.isfile(path):
            return read_file_safe(path) or ""
        return ""

    def _extract_description(self, xml_dir: str, script_name: str) -> str:
        """Extract description from the first comment in a Lua script."""
        content = self._read_script(xml_dir, script_name)
        if content:
            return self._extract_description_from_content(content)
        return ""

    def _extract_description_from_content(self, content: str) -> str:
        """Extract description from the first line comment of Lua content."""
        for line in content.split("\n"):
            stripped = line.strip()
            if stripped.startswith("--"):
                desc = stripped.lstrip("-").strip()
                if desc:
                    return desc
            elif stripped:
                break
        return ""

    def _extract_npc_keywords(self, lua_content: str) -> List[str]:
        """Extract conversation keywords from NPC Lua script."""
        keywords = []
        # Pattern: msgcontains(msg, "keyword")
        for m in re.finditer(r'msgcontains\s*\(\s*\w+\s*,\s*["\'](.+?)["\']\s*\)', lua_content):
            kw = m.group(1)
            if kw not in keywords:
                keywords.append(kw)
        # Pattern: msg == "keyword" or msg:lower() == "keyword"
        for m in re.finditer(r'msg(?::lower\(\))?\s*==\s*["\'](.+?)["\']\s*', lua_content):
            kw = m.group(1)
            if kw not in keywords:
                keywords.append(kw)
        return keywords
