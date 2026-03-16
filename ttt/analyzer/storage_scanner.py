"""
Storage ID scanner.

Detects:
  - All storage IDs used across the server
  - Conflicts: same storage ID used for different purposes
  - Free ranges: gaps in the storage ID space
"""

import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional

from ..utils import read_file_safe, find_lua_files


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class StorageUsage:
    """A single usage of a storage ID in a script."""
    filepath: str
    line: int
    storage_id: int
    context: str   # "get", "set", or the full matched line snippet
    line_text: str = ""


@dataclass
class StorageConflict:
    """A storage ID used in multiple unrelated scripts."""
    storage_id: int
    usages: List[StorageUsage]

    @property
    def file_count(self) -> int:
        return len(set(u.filepath for u in self.usages))


@dataclass
class StorageRange:
    """A free range in the storage ID space."""
    start: int
    end: int

    @property
    def size(self) -> int:
        return self.end - self.start + 1


@dataclass
class StorageReport:
    """Aggregated storage analysis."""
    all_usages: List[StorageUsage] = field(default_factory=list)
    conflicts: List[StorageConflict] = field(default_factory=list)
    free_ranges: List[StorageRange] = field(default_factory=list)
    total_unique_ids: int = 0
    total_scripts_scanned: int = 0
    min_id: int = 0
    max_id: int = 0

    @property
    def total_issues(self) -> int:
        return len(self.conflicts)

    def as_dict(self) -> Dict:
        return {
            "total_unique_ids": self.total_unique_ids,
            "total_scripts_scanned": self.total_scripts_scanned,
            "min_id": self.min_id,
            "max_id": self.max_id,
            "conflicts": [
                {"storage_id": c.storage_id, "file_count": c.file_count,
                 "usages": [{"file": u.filepath, "line": u.line, "context": u.context}
                            for u in c.usages]}
                for c in self.conflicts
            ],
            "free_ranges": [
                {"start": r.start, "end": r.end, "size": r.size}
                for r in self.free_ranges
            ],
            "all_ids": sorted(set(u.storage_id for u in self.all_usages)),
        }


# ---------------------------------------------------------------------------
# Storage ID extraction from Lua
# ---------------------------------------------------------------------------

# Patterns for getStorageValue / setStorageValue / getPlayerStorageValue etc.
_STORAGE_PATTERNS = [
    # OOP: player:getStorageValue(12345)  /  player:setStorageValue(12345, val)
    re.compile(
        r'\b\w+:(?:get|set)StorageValue\s*\(\s*(\d+)',
    ),
    # Procedural: getPlayerStorageValue(cid, 12345)  /  doPlayerSetStorageValue(cid, 12345, val)
    re.compile(
        r'\b(?:getPlayerStorageValue|doPlayerSetStorageValue|getCreatureStorage|'
        r'setPlayerStorageValue|doCreatureSetStorage)\s*\([^,]+,\s*(\d+)',
    ),
    # Global: getGlobalStorageValue(12345)  /  setGlobalStorageValue(12345, val)
    re.compile(
        r'\b(?:getGlobalStorageValue|setGlobalStorageValue|'
        r'Game\.getStorageValue|Game\.setStorageValue)\s*\(\s*(\d+)',
    ),
]

# Pattern for storage via constants  (STORAGE_QUEST = 50001)
_STORAGE_CONST_RE = re.compile(
    r'\b([A-Z_]+STORAGE[A-Z_]*|STOR_[A-Z_]+)\s*=\s*(\d+)',
)


def _extract_storage_ids(filepath: str, code: str) -> List[StorageUsage]:
    """Extract all storage ID usages from a Lua file."""
    usages = []
    lines = code.split("\n")

    for line_num, line_text in enumerate(lines, start=1):
        stripped = line_text.strip()
        # Skip comments
        if stripped.startswith("--"):
            continue

        for pattern in _STORAGE_PATTERNS:
            for m in pattern.finditer(line_text):
                try:
                    storage_id = int(m.group(1))
                except (ValueError, IndexError):
                    continue

                # Determine context
                if "set" in m.group(0).lower():
                    context = "set"
                else:
                    context = "get"

                usages.append(StorageUsage(
                    filepath=filepath,
                    line=line_num,
                    storage_id=storage_id,
                    context=context,
                    line_text=stripped,
                ))

    return usages


def _find_free_ranges(used_ids: Set[int], min_id: int = 10000,
                       max_id: int = 99999, max_ranges: int = 10) -> List[StorageRange]:
    """Find free (unused) ranges in the storage ID space."""
    if not used_ids:
        return [StorageRange(start=min_id, end=max_id)]

    sorted_ids = sorted(used_ids)
    actual_min = min(min_id, sorted_ids[0])
    actual_max = max(max_id, sorted_ids[-1] + 1000)

    ranges = []

    # Gap before first ID
    if sorted_ids[0] > actual_min + 1:
        ranges.append(StorageRange(start=actual_min, end=sorted_ids[0] - 1))

    # Gaps between consecutive IDs
    for i in range(len(sorted_ids) - 1):
        gap_start = sorted_ids[i] + 1
        gap_end = sorted_ids[i + 1] - 1
        if gap_end >= gap_start and (gap_end - gap_start) >= 9:
            ranges.append(StorageRange(start=gap_start, end=gap_end))

    # Gap after last ID
    if sorted_ids[-1] < actual_max:
        ranges.append(StorageRange(start=sorted_ids[-1] + 1, end=actual_max))

    # Sort by size descending and limit
    ranges.sort(key=lambda r: r.size, reverse=True)
    return ranges[:max_ranges]


# ---------------------------------------------------------------------------
# Main scanner
# ---------------------------------------------------------------------------

def scan_storage(directory: str) -> StorageReport:
    """Scan all Lua files for storage ID usage."""
    report = StorageReport()
    lua_files = find_lua_files(directory)
    report.total_scripts_scanned = len(lua_files)

    for filepath in lua_files:
        code = read_file_safe(filepath)
        if code is None:
            continue
        usages = _extract_storage_ids(filepath, code)
        report.all_usages.extend(usages)

    if not report.all_usages:
        return report

    # Unique IDs
    all_ids = set(u.storage_id for u in report.all_usages)
    report.total_unique_ids = len(all_ids)
    report.min_id = min(all_ids)
    report.max_id = max(all_ids)

    # Detect conflicts: same ID used in different files
    id_to_files: Dict[int, List[StorageUsage]] = defaultdict(list)
    for usage in report.all_usages:
        id_to_files[usage.storage_id].append(usage)

    for storage_id, usages in sorted(id_to_files.items()):
        unique_files = set(u.filepath for u in usages)
        if len(unique_files) > 1:
            report.conflicts.append(StorageConflict(
                storage_id=storage_id,
                usages=usages,
            ))

    # Free ranges
    report.free_ranges = _find_free_ranges(all_ids)

    return report
