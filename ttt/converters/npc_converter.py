"""
NPC Script Converter.

Converts TFS 0.3/0.4 NPC scripts to TFS 1.x format.

NPC structure in TFS 0.3/0.4:
    npc/
        npc_name.xml        (NPC definition: name, look, health, script reference)
        scripts/
            npc_name.lua    (NPC behavior: callbacks, NpcHandler, travel, shop, etc.)

The converter:
    1. Parses each NPC XML file for metadata (name, look, health, script path)
    2. Finds and transforms the linked Lua script using LuaTransformer
    3. Outputs the updated Lua script (API calls converted to 1.x OOP)
    4. Copies/updates the XML file with minor adjustments
"""

import os
import re
import logging
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

from ..utils import read_file_safe, write_file_safe
from ..report import FileReport

logger = logging.getLogger("ttt")


class NpcConverter:

    def __init__(self, lua_transformer=None, dry_run: bool = False):
        self.lua_transformer = lua_transformer
        self.dry_run = dry_run
        self.stats = {
            "npcs_converted": 0,
            "scripts_transformed": 0,
            "xml_copied": 0,
            "errors": 0,
        }
        self._file_reports: list = []

    def pop_file_reports(self) -> list:
        reports = self._file_reports[:]
        self._file_reports.clear()
        return reports

    def get_summary(self) -> str:
        parts = []
        if self.stats["npcs_converted"]:
            parts.append(f"{self.stats['npcs_converted']} NPC(s) converted")
        if self.stats["scripts_transformed"]:
            parts.append(f"{self.stats['scripts_transformed']} script(s) transformed")
        if self.stats["errors"]:
            parts.append(f"{self.stats['errors']} error(s)")
        return ", ".join(parts) if parts else "No NPCs found"

    def convert_npc_folder(self, npc_dir: str, scripts_dir: Optional[str],
                           npc_xml_files: List[str],
                           output_npc_dir: str) -> List[str]:
        output_files = []

        if not scripts_dir:
            scripts_dir = npc_dir

        for xml_path in npc_xml_files:
            try:
                files = self._convert_single_npc(xml_path, scripts_dir, output_npc_dir)
                output_files.extend(files)
            except Exception as e:
                logger.error(f"    Error converting NPC {os.path.basename(xml_path)}: {e}")
                self.stats["errors"] += 1
                self._file_reports.append(FileReport(
                    source_path=xml_path,
                    error=str(e),
                    success=False,
                ))

        return output_files

    def _convert_single_npc(self, xml_path: str, scripts_dir: str,
                            output_npc_dir: str) -> List[str]:
        output_files = []

        # Parse the NPC XML
        xml_content = read_file_safe(xml_path)
        if not xml_content:
            return []

        npc_info = self._parse_npc_xml(xml_content, xml_path)
        if not npc_info:
            return []

        npc_name = npc_info.get("name", "Unknown")
        script_name = npc_info.get("script", "")

        logger.debug(f"    NPC: {npc_name} (script: {script_name})")

        # Converte o Lua
        if script_name:
            lua_path = os.path.join(scripts_dir, script_name)
            if not os.path.exists(lua_path):
                # Try common alternate locations
                lua_path = self._find_npc_script(scripts_dir, script_name,
                                                  os.path.dirname(xml_path))
            if lua_path and os.path.exists(lua_path):
                files = self._convert_npc_script(lua_path, npc_info, output_npc_dir)
                output_files.extend(files)
            else:
                logger.warning(f"    NPC script not found: {script_name} (NPC: {npc_name})")
                self.stats["errors"] += 1
                self._file_reports.append(FileReport(
                    source_path=os.path.join(scripts_dir, script_name),
                    error=f"Script not found: {script_name}",
                    success=False,
                ))

        # Copia/atualiza o XML
        if not self.dry_run and output_npc_dir:
            out_xml = os.path.join(output_npc_dir, os.path.basename(xml_path))
            write_file_safe(out_xml, xml_content)
            output_files.append(out_xml)
            self.stats["xml_copied"] += 1

        self.stats["npcs_converted"] += 1
        return output_files

    def _convert_npc_script(self, lua_path: str, npc_info: Dict,
                            output_npc_dir: str) -> List[str]:
        lua_code = read_file_safe(lua_path)
        if not lua_code:
            return []

        original_code = lua_code
        fr = FileReport(source_path=lua_path)
        fr.file_type = "npc"
        fr.conversion_type = "npc_script"

        script_name = os.path.basename(lua_path)

        if self.lua_transformer:
            lua_code = self.lua_transformer.transform(lua_code, script_name)
            fr.functions_converted = self.lua_transformer.stats.get("functions_converted", 0)
            fr.signatures_updated = self.lua_transformer.stats.get("signatures_updated", 0)
            fr.constants_replaced = self.lua_transformer.stats.get("constants_replaced", 0)
            fr.variables_renamed = self.lua_transformer.stats.get("variables_renamed", 0)
            fr.warnings = list(self.lua_transformer.warnings)

        if not lua_code.startswith("-- NPC:"):
            header = self._generate_npc_header(npc_info)
            lua_code = header + lua_code

        # Write output
        out_scripts_dir = os.path.join(output_npc_dir, "scripts") if output_npc_dir else ""
        out_path = os.path.join(out_scripts_dir, script_name) if out_scripts_dir else ""

        if not self.dry_run and out_path:
            write_file_safe(out_path, lua_code)
            fr.output_path = out_path

        fr.ttt_warnings = lua_code.count("-- TTT:")
        fr.original_content = original_code
        fr.converted_content = lua_code
        self._file_reports.append(fr)
        self.stats["scripts_transformed"] += 1

        return [out_path] if out_path and not self.dry_run else []

    def _parse_npc_xml(self, xml_content: str, xml_path: str) -> Optional[Dict]:
        try:
            # Clean up XML for common issues
            clean = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', xml_content)
            root = ET.fromstring(clean)
        except ET.ParseError:
            # Try wrapping in root element
            try:
                wrapped = f"<root>{xml_content}</root>"
                wrapped = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', wrapped)
                root = ET.fromstring(wrapped)
                root = root[0] if len(root) > 0 else root
            except ET.ParseError as e:
                logger.warning(f"    Could not parse NPC XML: {xml_path} ({e})")
                return None

        if root.tag.lower() != "npc":
            # Look for <npc> child
            npc_elem = root.find(".//npc")
            if npc_elem is None:
                npc_elem = root.find(".//Npc")
            if npc_elem is None:
                logger.warning(f"    No <npc> element found in: {xml_path}")
                return None
            root = npc_elem

        info = dict(root.attrib)

        # Extract look info
        look_elem = root.find(".//look")
        if look_elem is None:
            look_elem = root.find(".//Look")
        if look_elem is not None:
            info["look"] = dict(look_elem.attrib)

        # Extract health info
        health_elem = root.find(".//health")
        if health_elem is None:
            health_elem = root.find(".//Health")
        if health_elem is not None:
            info["health"] = dict(health_elem.attrib)

        # Extract parameters
        params = {}
        for param in root.findall(".//parameter"):
            key = param.get("key", "")
            value = param.get("value", "")
            if key:
                params[key] = value
        if params:
            info["parameters"] = params

        return info

    def _generate_npc_header(self, npc_info: Dict) -> str:
        lines = []
        name = npc_info.get("name", "Unknown")
        lines.append(f"-- NPC: {name}")

        look = npc_info.get("look", {})
        if look:
            look_parts = []
            if "type" in look:
                look_parts.append(f"type={look['type']}")
            if "head" in look:
                look_parts.append(f"head={look['head']}")
            if "body" in look:
                look_parts.append(f"body={look['body']}")
            if "legs" in look:
                look_parts.append(f"legs={look['legs']}")
            if "feet" in look:
                look_parts.append(f"feet={look['feet']}")
            if look_parts:
                lines.append(f"-- Look: {', '.join(look_parts)}")

        health = npc_info.get("health", {})
        if health:
            lines.append(f"-- Health: {health.get('now', '?')}/{health.get('max', '?')}")

        walkinterval = npc_info.get("walkinterval")
        if walkinterval:
            lines.append(f"-- Walk interval: {walkinterval}")

        lines.append("")
        return "\n".join(lines) + "\n"

    def _find_npc_script(self, scripts_dir: str, script_name: str,
                         xml_dir: str) -> Optional[str]:
        candidates = [
            os.path.join(scripts_dir, script_name),
            os.path.join(xml_dir, "scripts", script_name),
            os.path.join(xml_dir, script_name),
        ]

        # Also try without subdirectory prefix in script_name
        base_name = os.path.basename(script_name)
        candidates.extend([
            os.path.join(scripts_dir, base_name),
            os.path.join(xml_dir, "scripts", base_name),
        ])

        for c in candidates:
            if os.path.isfile(c):
                return c

        # Walk the scripts dir looking for a match by basename
        if os.path.isdir(scripts_dir):
            for root, _, files in os.walk(scripts_dir):
                for f in files:
                    if f.lower() == base_name.lower():
                        return os.path.join(root, f)

        return None
