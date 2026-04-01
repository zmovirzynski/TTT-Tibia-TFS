"""
Item usage analyzer.

Detects:
  - All item IDs referenced in Lua scripts
  - All item IDs registered in XML files (actions, movements)
  - Items referenced in scripts but not registered in XML
  - Items registered in XML but whose scripts don't use them
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List, Set

from ..utils import read_file_safe, find_lua_files
from ..scanner import scan_directory


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class ItemReference:
    """A reference to an item ID in code or XML."""
    item_id: int
    filepath: str
    line: int
    source: str  # "lua" or "xml"
    context: str  # e.g. "addItem", "removeItem", "itemid attr"


@dataclass
class ItemUsageReport:
    """Aggregated item usage analysis."""
    all_references: List[ItemReference] = field(default_factory=list)
    lua_only_ids: Set[int] = field(default_factory=set)
    xml_only_ids: Set[int] = field(default_factory=set)
    both_ids: Set[int] = field(default_factory=set)
    total_unique_ids: int = 0
    total_scripts_scanned: int = 0

    @property
    def total_issues(self) -> int:
        """Items only in one source are points of interest."""
        return len(self.lua_only_ids) + len(self.xml_only_ids)

    def as_dict(self) -> Dict:
        return {
            "total_unique_ids": self.total_unique_ids,
            "total_scripts_scanned": self.total_scripts_scanned,
            "lua_only_ids": sorted(self.lua_only_ids),
            "xml_only_ids": sorted(self.xml_only_ids),
            "both_ids": sorted(self.both_ids),
            "lua_only_count": len(self.lua_only_ids),
            "xml_only_count": len(self.xml_only_ids),
            "both_count": len(self.both_ids),
        }


# ---------------------------------------------------------------------------
# Item ID extraction from Lua
# ---------------------------------------------------------------------------

# Patterns for item IDs in Lua code
_LUA_ITEM_PATTERNS = [
    # addItem(itemId, count) / player:addItem(1234, 1)
    re.compile(r'\baddItem\s*\(\s*(\d{3,5})', re.IGNORECASE),
    # doPlayerAddItem(cid, 1234, ...) / doCreateItem(1234, ...)
    re.compile(r'\b(?:doPlayerAddItem|doCreateItem|doCreateItemEx)\s*\([^,]*,\s*(\d{3,5})'),
    # Item(1234)
    re.compile(r'\bItem\s*\(\s*(\d{3,5})'),
    # removeItem / doRemoveItem  (item.uid is not an item ID)
    # item:getId() == 1234
    re.compile(r':getId\s*\(\s*\)\s*[=~<>]+\s*(\d{3,5})'),
    # action:id(1234) / movement:id(1234)
    re.compile(r':id\s*\(\s*(\d{3,5})'),
    # getItemIdByName results compared
    re.compile(r'itemid\s*==?\s*(\d{3,5})', re.IGNORECASE),
    re.compile(r'item\.itemid\s*==?\s*(\d{3,5})', re.IGNORECASE),
]

# XML patterns
_XML_ITEMID_RE = re.compile(r'itemid\s*=\s*"([^"]*)"', re.IGNORECASE)
_XML_FROMID_RE = re.compile(r'fromid\s*=\s*"(\d+)"', re.IGNORECASE)
_XML_TOID_RE = re.compile(r'toid\s*=\s*"(\d+)"', re.IGNORECASE)


def _extract_lua_item_ids(filepath: str, code: str) -> List[ItemReference]:
    """Extract item ID references from Lua code."""
    refs = []
    lines = code.split("\n")

    for line_num, line_text in enumerate(lines, start=1):
        stripped = line_text.strip()
        if stripped.startswith("--"):
            continue

        for pattern in _LUA_ITEM_PATTERNS:
            for m in pattern.finditer(line_text):
                try:
                    item_id = int(m.group(1))
                except (ValueError, IndexError):
                    continue
                # Skip very low IDs (likely not item IDs)
                if item_id < 100:
                    continue
                refs.append(ItemReference(
                    item_id=item_id,
                    filepath=filepath,
                    line=line_num,
                    source="lua",
                    context=m.group(0).strip()[:60],
                ))

    return refs


def _extract_xml_item_ids(xml_path: str) -> List[ItemReference]:
    """Extract item IDs from XML registration files."""
    refs = []
    content = read_file_safe(xml_path)
    if not content:
        return refs

    for line_num, line_text in enumerate(content.split("\n"), start=1):
        for pattern in (_XML_ITEMID_RE, _XML_FROMID_RE, _XML_TOID_RE):
            for m in pattern.finditer(line_text):
                raw = m.group(1)
                # Handle semicolon-separated IDs
                for id_str in raw.split(";"):
                    id_str = id_str.strip()
                    if id_str and id_str.isdigit():
                        item_id = int(id_str)
                        if item_id >= 100:
                            refs.append(ItemReference(
                                item_id=item_id,
                                filepath=xml_path,
                                line=line_num,
                                source="xml",
                                context=f"{pattern.pattern[:30]}",
                            ))

    return refs


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------

def scan_item_usage(directory: str) -> ItemUsageReport:
    """Scan all files for item ID usage."""
    scan = scan_directory(directory)
    report = ItemUsageReport()

    lua_files = find_lua_files(directory)
    report.total_scripts_scanned = len(lua_files)

    lua_ids: Set[int] = set()
    xml_ids: Set[int] = set()

    # Lua files
    for filepath in lua_files:
        code = read_file_safe(filepath)
        if code is None:
            continue
        refs = _extract_lua_item_ids(filepath, code)
        report.all_references.extend(refs)
        lua_ids.update(r.item_id for r in refs)

    # XML registration files
    for xml_attr in ("actions_xml", "movements_xml", "talkactions_xml",
                     "creaturescripts_xml", "globalevents_xml"):
        xml_path = getattr(scan, xml_attr, None)
        if xml_path:
            refs = _extract_xml_item_ids(xml_path)
            report.all_references.extend(refs)
            xml_ids.update(r.item_id for r in refs)

    # Compute sets
    report.both_ids = lua_ids & xml_ids
    report.lua_only_ids = lua_ids - xml_ids
    report.xml_only_ids = xml_ids - lua_ids
    report.total_unique_ids = len(lua_ids | xml_ids)

    return report
