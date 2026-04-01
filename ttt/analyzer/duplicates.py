"""
Duplicate detector.

Detects:
  - Scripts with identical or near-identical content
  - TalkActions with the same keyword registered
  - Actions registered on the same item ID
  - Movements registered on the same item/action ID
"""

import re
import hashlib
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..utils import read_file_safe, find_lua_files, find_xml_files
from ..scanner import scan_directory


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DuplicateScript:
    """A group of scripts with identical or near-identical content."""
    file_hash: str
    filepaths: List[str]
    similarity: float = 1.0  # 1.0 = identical

    @property
    def count(self) -> int:
        return len(self.filepaths)


@dataclass
class DuplicateRegistration:
    """A registration key that appears more than once (e.g. same item ID)."""
    reg_type: str  # "action-itemid", "talkaction-keyword", "movement-itemid"
    key: str       # The duplicated key value
    entries: List[Dict[str, str]]  # list of {xml_file, script, line, ...}


@dataclass
class DuplicateReport:
    """Aggregated duplicate analysis."""
    duplicate_scripts: List[DuplicateScript] = field(default_factory=list)
    duplicate_registrations: List[DuplicateRegistration] = field(default_factory=list)
    total_scripts_scanned: int = 0
    total_xml_scanned: int = 0

    @property
    def total_issues(self) -> int:
        return len(self.duplicate_scripts) + len(self.duplicate_registrations)

    @property
    def total_duplicate_files(self) -> int:
        return sum(d.count - 1 for d in self.duplicate_scripts)

    def as_dict(self) -> Dict:
        return {
            "duplicate_scripts": [
                {"hash": d.file_hash, "files": d.filepaths,
                 "count": d.count, "similarity": d.similarity}
                for d in self.duplicate_scripts
            ],
            "duplicate_registrations": [
                {"type": d.reg_type, "key": d.key, "entries": d.entries}
                for d in self.duplicate_registrations
            ],
            "total_scripts_scanned": self.total_scripts_scanned,
            "total_xml_scanned": self.total_xml_scanned,
            "total_issues": self.total_issues,
            "total_duplicate_files": self.total_duplicate_files,
        }


# ---------------------------------------------------------------------------
# Content hashing / similarity
# ---------------------------------------------------------------------------

def _normalize_code(code: str) -> str:
    """Normalize code for comparison: strip comments, blank lines, whitespace."""
    lines = []
    in_block_comment = False
    for line in code.split("\n"):
        stripped = line.strip()
        # Handle block comments --[[ ... ]]
        if in_block_comment:
            if "]]" in stripped:
                in_block_comment = False
            continue
        if stripped.startswith("--[["):
            in_block_comment = True
            continue
        # Skip line comments and blank lines
        if stripped.startswith("--") or not stripped:
            continue
        # Remove inline comments
        comment_pos = _find_comment_pos(stripped)
        if comment_pos >= 0:
            stripped = stripped[:comment_pos].rstrip()
        if stripped:
            lines.append(stripped)
    return "\n".join(lines)


def _find_comment_pos(line: str) -> int:
    """Find position of -- comment in a line, respecting strings."""
    in_str = None
    i = 0
    while i < len(line):
        ch = line[i]
        if in_str:
            if ch == in_str and (i == 0 or line[i-1] != '\\'):
                in_str = None
        elif ch in ('"', "'"):
            in_str = ch
        elif ch == '-' and i + 1 < len(line) and line[i+1] == '-':
            return i
        i += 1
    return -1


def _hash_code(code: str) -> str:
    """Hash normalized code to detect identical scripts."""
    normalized = _normalize_code(code)
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def _similarity_ratio(code1: str, code2: str) -> float:
    """Compute a rough similarity ratio between two code strings (0-1)."""
    norm1 = _normalize_code(code1)
    norm2 = _normalize_code(code2)
    if norm1 == norm2:
        return 1.0

    lines1 = set(norm1.split("\n"))
    lines2 = set(norm2.split("\n"))
    if not lines1 and not lines2:
        return 1.0
    intersection = lines1 & lines2
    union = lines1 | lines2
    if not union:
        return 1.0
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# XML registration extraction
# ---------------------------------------------------------------------------

def _extract_action_registrations(xml_path: str) -> List[Dict[str, str]]:
    """Extract action registrations from actions.xml."""
    entries = []
    content = read_file_safe(xml_path)
    if not content:
        return entries
    for i, line in enumerate(content.split("\n"), start=1):
        m = re.search(r'<action\s+', line, re.IGNORECASE)
        if not m:
            continue
        script_m = re.search(r'script\s*=\s*"([^"]*)"', line, re.IGNORECASE)
        script = script_m.group(1) if script_m else ""

        # itemid can be single or semicolon-separated
        itemid_m = re.search(r'itemid\s*=\s*"([^"]*)"', line, re.IGNORECASE)
        if itemid_m:
            ids = [x.strip() for x in itemid_m.group(1).split(";") if x.strip()]
            for item_id in ids:
                entries.append({"type": "action-itemid", "key": item_id,
                                "script": script, "line": str(i),
                                "xml_file": xml_path})

        actionid_m = re.search(r'actionid\s*=\s*"([^"]*)"', line, re.IGNORECASE)
        if actionid_m:
            ids = [x.strip() for x in actionid_m.group(1).split(";") if x.strip()]
            for aid in ids:
                entries.append({"type": "action-actionid", "key": aid,
                                "script": script, "line": str(i),
                                "xml_file": xml_path})

        uniqueid_m = re.search(r'uniqueid\s*=\s*"([^"]*)"', line, re.IGNORECASE)
        if uniqueid_m:
            ids = [x.strip() for x in uniqueid_m.group(1).split(";") if x.strip()]
            for uid in ids:
                entries.append({"type": "action-uniqueid", "key": uid,
                                "script": script, "line": str(i),
                                "xml_file": xml_path})
    return entries


def _extract_talkaction_registrations(xml_path: str) -> List[Dict[str, str]]:
    """Extract talkaction registrations from talkactions.xml."""
    entries = []
    content = read_file_safe(xml_path)
    if not content:
        return entries
    for i, line in enumerate(content.split("\n"), start=1):
        m = re.search(r'<talkaction\s+', line, re.IGNORECASE)
        if not m:
            continue
        script_m = re.search(r'script\s*=\s*"([^"]*)"', line, re.IGNORECASE)
        script = script_m.group(1) if script_m else ""

        words_m = re.search(r'words\s*=\s*"([^"]*)"', line, re.IGNORECASE)
        if words_m:
            keyword = words_m.group(1).strip()
            entries.append({"type": "talkaction-keyword", "key": keyword,
                            "script": script, "line": str(i),
                            "xml_file": xml_path})
    return entries


def _extract_movement_registrations(xml_path: str) -> List[Dict[str, str]]:
    """Extract movement registrations from movements.xml."""
    entries = []
    content = read_file_safe(xml_path)
    if not content:
        return entries
    for i, line in enumerate(content.split("\n"), start=1):
        m = re.search(r'<movevent\s+', line, re.IGNORECASE)
        if not m:
            continue
        script_m = re.search(r'script\s*=\s*"([^"]*)"', line, re.IGNORECASE)
        script = script_m.group(1) if script_m else ""

        type_m = re.search(r'type\s*=\s*"([^"]*)"', line, re.IGNORECASE)
        event_type = type_m.group(1) if type_m else ""

        for attr in ("itemid", "actionid", "uniqueid"):
            attr_m = re.search(attr + r'\s*=\s*"([^"]*)"', line, re.IGNORECASE)
            if attr_m:
                ids = [x.strip() for x in attr_m.group(1).split(";") if x.strip()]
                for mid in ids:
                    entries.append({
                        "type": f"movement-{attr}",
                        "key": f"{mid} ({event_type})",
                        "script": script, "line": str(i),
                        "xml_file": xml_path,
                    })
    return entries


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------

def detect_duplicates(directory: str) -> DuplicateReport:
    """Run the full duplicate detection on a server directory."""
    scan = scan_directory(directory)
    report = DuplicateReport()

    lua_files = find_lua_files(directory)
    xml_files = find_xml_files(directory)
    report.total_scripts_scanned = len(lua_files)
    report.total_xml_scanned = len(xml_files)

    # 1) Detect identical / near-identical scripts
    hash_map: Dict[str, List[str]] = defaultdict(list)  # hash -> [filepaths]

    for filepath in lua_files:
        code = read_file_safe(filepath)
        if code is None:
            continue
        code_hash = _hash_code(code)
        hash_map[code_hash].append(filepath)

    for code_hash, filepaths in hash_map.items():
        if len(filepaths) > 1:
            report.duplicate_scripts.append(DuplicateScript(
                file_hash=code_hash,
                filepaths=sorted(filepaths),
                similarity=1.0,
            ))

    # 2) Detect duplicate XML registrations
    all_registrations: List[Dict[str, str]] = []

    if scan.actions_xml:
        all_registrations.extend(_extract_action_registrations(scan.actions_xml))
    if scan.talkactions_xml:
        all_registrations.extend(_extract_talkaction_registrations(scan.talkactions_xml))
    if scan.movements_xml:
        all_registrations.extend(_extract_movement_registrations(scan.movements_xml))

    # Group by (type, key) and find duplicates
    reg_groups: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
    for reg in all_registrations:
        group_key = (reg["type"], reg["key"])
        reg_groups[group_key].append(reg)

    for (reg_type, key), entries in reg_groups.items():
        if len(entries) > 1:
            report.duplicate_registrations.append(DuplicateRegistration(
                reg_type=reg_type,
                key=key,
                entries=entries,
            ))

    return report


# ── Semantic duplicate detection (AST-backed) ─────────────────────────────

@dataclass
class SemanticDuplicate:
    """Two files that are structurally identical despite different variable names."""
    file_a: str
    file_b: str
    similarity: float


def detect_semantic_duplicates(
    lua_files: List[str],
    threshold: float = 0.90,
) -> List["SemanticDuplicate"]:
    """Compare all pairs of Lua files for structural similarity via AST normalization.

    Returns pairs above threshold similarity, sorted by similarity descending.
    Falls back to empty list if luaparser is unavailable.
    """
    try:
        from ttt.converters.ast_normalizer import structural_similarity
    except ImportError:
        return []

    codes = {}
    for path in lua_files:
        try:
            with open(path, encoding="utf-8", errors="replace") as f:
                codes[path] = f.read()
        except OSError:
            continue

    paths = list(codes.keys())
    results = []
    for i in range(len(paths)):
        for j in range(i + 1, len(paths)):
            score = structural_similarity(codes[paths[i]], codes[paths[j]])
            if score >= threshold:
                results.append(SemanticDuplicate(
                    file_a=paths[i],
                    file_b=paths[j],
                    similarity=score,
                ))
    return sorted(results, key=lambda x: -x.similarity)
