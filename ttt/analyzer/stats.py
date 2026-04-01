"""
Server statistics collector.

Collects:
  - Total scripts by type (action, movement, spell, etc.)
  - Top N most-used functions
  - API style distribution (old procedural vs OOP)
  - Lines of code totals
"""

import os
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from ..utils import read_file_safe, find_lua_files
from ..scanner import scan_directory, ScanResult
from ..mappings.tfs03_functions import TFS03_TO_1X
from ..mappings.tfs04_functions import TFS04_TO_1X


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class ScriptTypeCount:
    """Counts per script category."""

    actions: int = 0
    movements: int = 0
    talkactions: int = 0
    creaturescripts: int = 0
    globalevents: int = 0
    spells: int = 0
    npcs: int = 0
    other: int = 0

    @property
    def total(self) -> int:
        return (
            self.actions
            + self.movements
            + self.talkactions
            + self.creaturescripts
            + self.globalevents
            + self.spells
            + self.npcs
            + self.other
        )

    def as_dict(self) -> Dict[str, int]:
        return {
            "actions": self.actions,
            "movements": self.movements,
            "talkactions": self.talkactions,
            "creaturescripts": self.creaturescripts,
            "globalevents": self.globalevents,
            "spells": self.spells,
            "npcs": self.npcs,
            "other": self.other,
            "total": self.total,
        }


@dataclass
class ServerStats:
    """Aggregated server statistics."""

    root_dir: str = ""
    script_counts: ScriptTypeCount = field(default_factory=ScriptTypeCount)
    total_lua_files: int = 0
    total_xml_files: int = 0
    total_lines: int = 0
    total_code_lines: int = 0  # non-blank, non-comment
    total_functions_defined: int = 0
    function_calls: Counter = field(default_factory=Counter)
    api_style: Dict[str, int] = field(
        default_factory=lambda: {"procedural": 0, "oop": 0, "mixed": 0, "unknown": 0}
    )
    version_hints: List[str] = field(default_factory=list)

    def top_functions(self, n: int = 20) -> List[Tuple[str, int]]:
        """Return the N most-called functions."""
        return self.function_calls.most_common(n)

    def as_dict(self) -> Dict:
        return {
            "root_dir": self.root_dir,
            "script_counts": self.script_counts.as_dict(),
            "total_lua_files": self.total_lua_files,
            "total_xml_files": self.total_xml_files,
            "total_lines": self.total_lines,
            "total_code_lines": self.total_code_lines,
            "total_functions_defined": self.total_functions_defined,
            "top_functions": self.top_functions(20),
            "api_style": dict(self.api_style),
            "version_hints": self.version_hints,
        }


# ---------------------------------------------------------------------------
# Function-call extraction
# ---------------------------------------------------------------------------

# Matches  word(  or  obj:method(
_FUNC_CALL_RE = re.compile(
    r"(?<![.\w])([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?::[A-Za-z_]\w*)?)\s*\(",
)

# Matches function definitions
_FUNC_DEF_RE = re.compile(
    r"^\s*(?:local\s+)?function\s+",
    re.MULTILINE,
)

# Old procedural API set (for style detection)
_OLD_API_CALLS = set(TFS03_TO_1X.keys()) | set(TFS04_TO_1X.keys())

# OOP patterns
_OOP_PATTERN = re.compile(r"\b\w+:\w+\(")

# RevScript pattern
_REVSCRIPT_PATTERN = re.compile(
    r"\b(?:Action|MoveEvent|TalkAction|CreatureEvent|GlobalEvent|Spell)\s*\("
)


def _is_comment_or_string_line(line: str) -> bool:
    """A very rough check for pure-comment or pure-blank lines."""
    stripped = line.strip()
    if not stripped:
        return True
    if stripped.startswith("--"):
        return True
    return False


def _classify_file_style(code: str) -> str:
    """Classify a file as procedural / oop / mixed / unknown."""
    has_old = False
    has_oop = False

    for name in _OLD_API_CALLS:
        if re.search(r"\b" + re.escape(name) + r"\s*\(", code):
            has_old = True
            break

    if _OOP_PATTERN.search(code):
        has_oop = True

    if has_old and has_oop:
        return "mixed"
    elif has_old:
        return "procedural"
    elif has_oop:
        return "oop"
    return "unknown"


def _extract_function_calls(code: str) -> Counter:
    """Extract all function calls from Lua code, skipping strings/comments."""
    calls: Counter = Counter()
    lines = code.split("\n")

    for line in lines:
        # Strip inline comments  (-- ...)
        comment_pos = -1
        in_str = None
        for i, ch in enumerate(line):
            if in_str:
                if ch == in_str and (i == 0 or line[i - 1] != "\\"):
                    in_str = None
            elif ch in ('"', "'"):
                in_str = ch
            elif ch == "-" and i + 1 < len(line) and line[i + 1] == "-":
                comment_pos = i
                break

        if comment_pos == 0:
            continue
        code_part = line[:comment_pos] if comment_pos > 0 else line

        for m in _FUNC_CALL_RE.finditer(code_part):
            name = m.group(1)
            # Skip common Lua built-ins that aren't interesting
            if name in (
                "if",
                "elseif",
                "while",
                "for",
                "return",
                "not",
                "and",
                "or",
                "function",
                "local",
                "end",
                "then",
                "do",
                "else",
                "repeat",
                "until",
                "in",
                "true",
                "false",
                "nil",
                "print",
            ):
                continue
            calls[name] += 1

    return calls


# ---------------------------------------------------------------------------
# Script-type classification
# ---------------------------------------------------------------------------


def _classify_script(filepath: str, scan: ScanResult) -> str:
    """Classify a Lua file by its type based on directory location."""
    norm = os.path.normpath(filepath).lower()

    dir_map = {
        "actions": scan.actions_dir,
        "movements": scan.movements_dir,
        "talkactions": scan.talkactions_dir,
        "creaturescripts": scan.creaturescripts_dir,
        "globalevents": scan.globalevents_dir,
    }

    for category, dir_path in dir_map.items():
        if dir_path and norm.startswith(os.path.normpath(dir_path).lower()):
            return category

    # NPC
    for npc_path in (scan.npc_dir, scan.npc_scripts_dir):
        if npc_path and norm.startswith(os.path.normpath(npc_path).lower()):
            return "npcs"

    # Check by parent directory names
    parts = norm.replace("\\", "/").split("/")
    for part in parts:
        if part in ("actions", "action"):
            return "actions"
        if part in ("movements", "movement"):
            return "movements"
        if part in ("talkactions", "talkaction"):
            return "talkactions"
        if part in ("creaturescripts", "creaturescript"):
            return "creaturescripts"
        if part in ("globalevents", "globalevent"):
            return "globalevents"
        if part in ("spells", "spell"):
            return "spells"
        if part in ("npc", "npcs"):
            return "npcs"

    # Try content-based detection
    code = read_file_safe(filepath)
    if code:
        if _REVSCRIPT_PATTERN.search(code):
            # Determine from the RevScript class used
            if re.search(r"\bAction\s*\(", code):
                return "actions"
            if re.search(r"\bMoveEvent\s*\(", code):
                return "movements"
            if re.search(r"\bTalkAction\s*\(", code):
                return "talkactions"
            if re.search(r"\bCreatureEvent\s*\(", code):
                return "creaturescripts"
            if re.search(r"\bGlobalEvent\s*\(", code):
                return "globalevents"
            if re.search(r"\bSpell\s*\(", code):
                return "spells"

    return "other"


# ---------------------------------------------------------------------------
# Main collector
# ---------------------------------------------------------------------------


def collect_stats(directory: str) -> ServerStats:
    """Collect full server statistics for a directory."""
    scan = scan_directory(directory)
    stats = ServerStats(root_dir=directory)
    stats.version_hints = scan.version_hints
    stats.total_xml_files = len(scan.xml_files)

    lua_files = find_lua_files(directory)
    stats.total_lua_files = len(lua_files)

    counts = ScriptTypeCount()

    for filepath in lua_files:
        code = read_file_safe(filepath)
        if code is None:
            continue

        # Lines
        lines = code.split("\n")
        stats.total_lines += len(lines)
        stats.total_code_lines += sum(
            1 for ln in lines if not _is_comment_or_string_line(ln)
        )

        # Functions defined
        stats.total_functions_defined += len(_FUNC_DEF_RE.findall(code))

        # Function calls
        stats.function_calls += _extract_function_calls(code)

        # API style
        style = _classify_file_style(code)
        stats.api_style[style] += 1

        # Script type
        category = _classify_script(filepath, scan)
        if category == "actions":
            counts.actions += 1
        elif category == "movements":
            counts.movements += 1
        elif category == "talkactions":
            counts.talkactions += 1
        elif category == "creaturescripts":
            counts.creaturescripts += 1
        elif category == "globalevents":
            counts.globalevents += 1
        elif category == "spells":
            counts.spells += 1
        elif category == "npcs":
            counts.npcs += 1
        else:
            counts.other += 1

    stats.script_counts = counts
    return stats
