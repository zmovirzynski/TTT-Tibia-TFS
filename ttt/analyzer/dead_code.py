"""
Dead code detector.

Detects:
  - Lua scripts never referenced in any XML registration file
  - Functions defined but never called within the project
  - XML entries that reference scripts that don't exist on disk
"""

import os
import re
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple

from ..utils import read_file_safe, find_lua_files, find_xml_files
from ..scanner import scan_directory, ScanResult


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class OrphanScript:
    """A Lua script file that is not referenced in any XML."""

    filepath: str
    category: str  # actions, movements, etc.
    reason: str = "Not referenced in any XML registration file"


@dataclass
class BrokenXmlRef:
    """An XML entry referencing a script that doesn't exist."""

    xml_file: str
    script_ref: str
    expected_path: str
    line: int = 0


@dataclass
class UnusedFunction:
    """A function defined but never called anywhere in the project."""

    filepath: str
    function_name: str
    line: int


@dataclass
class DeadCodeReport:
    """Aggregated dead code report."""

    orphan_scripts: List[OrphanScript] = field(default_factory=list)
    broken_xml_refs: List[BrokenXmlRef] = field(default_factory=list)
    unused_functions: List[UnusedFunction] = field(default_factory=list)
    total_scripts_scanned: int = 0
    total_xml_scanned: int = 0

    @property
    def total_issues(self) -> int:
        return (
            len(self.orphan_scripts)
            + len(self.broken_xml_refs)
            + len(self.unused_functions)
        )

    def as_dict(self) -> Dict:
        return {
            "orphan_scripts": [
                {"filepath": o.filepath, "category": o.category, "reason": o.reason}
                for o in self.orphan_scripts
            ],
            "broken_xml_refs": [
                {
                    "xml_file": b.xml_file,
                    "script_ref": b.script_ref,
                    "expected_path": b.expected_path,
                    "line": b.line,
                }
                for b in self.broken_xml_refs
            ],
            "unused_functions": [
                {
                    "filepath": u.filepath,
                    "function_name": u.function_name,
                    "line": u.line,
                }
                for u in self.unused_functions
            ],
            "total_scripts_scanned": self.total_scripts_scanned,
            "total_xml_scanned": self.total_xml_scanned,
            "total_issues": self.total_issues,
        }


# ---------------------------------------------------------------------------
# XML script reference extraction
# ---------------------------------------------------------------------------


def _extract_xml_script_refs(xml_path: str) -> List[Tuple[str, int]]:
    """Extract all 'script' attribute values from an XML file.
    Returns list of (script_name, line_number)."""
    refs = []
    try:
        # Parse line-by-line for line number tracking
        content = read_file_safe(xml_path)
        if not content:
            return refs
        for i, line in enumerate(content.split("\n"), start=1):
            m = re.search(r'script\s*=\s*"([^"]+)"', line, re.IGNORECASE)
            if m:
                refs.append((m.group(1), i))
    except Exception:
        pass
    return refs


def _resolve_script_path(xml_path: str, script_ref: str, scan: ScanResult) -> str:
    """Resolve a script reference from XML to an absolute path."""
    xml_dir = os.path.dirname(xml_path)
    xml_basename = os.path.basename(xml_path).lower()

    # Map XML file to its scripts directory
    dir_map = {
        "actions.xml": scan.actions_dir,
        "movements.xml": scan.movements_dir,
        "talkactions.xml": scan.talkactions_dir,
        "creaturescripts.xml": scan.creaturescripts_dir,
        "globalevents.xml": scan.globalevents_dir,
    }

    scripts_dir = dir_map.get(xml_basename)
    if scripts_dir:
        return os.path.normpath(os.path.join(scripts_dir, script_ref))

    # Fallback: look in scripts/ subdirectory or same directory
    scripts_subdir = os.path.join(xml_dir, "scripts")
    if os.path.isdir(scripts_subdir):
        return os.path.normpath(os.path.join(scripts_subdir, script_ref))
    return os.path.normpath(os.path.join(xml_dir, script_ref))


# ---------------------------------------------------------------------------
# Function definition / call analysis
# ---------------------------------------------------------------------------

_FUNC_DEF_RE = re.compile(
    r"^\s*(?:local\s+)?function\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?::[A-Za-z_]\w*)?)\s*\(",
    re.MULTILINE,
)

# Standard callbacks that are expected (not dead even if not called directly)
_KNOWN_CALLBACKS = {
    "onUse",
    "onSay",
    "onLogin",
    "onLogout",
    "onDeath",
    "onKill",
    "onThink",
    "onStepIn",
    "onStepOut",
    "onEquip",
    "onDeEquip",
    "onAddItem",
    "onRemoveItem",
    "onStartup",
    "onShutdown",
    "onRecord",
    "onTime",
    "onPrepareDeath",
    "onAdvance",
    "onTextEdit",
    "onHealthChange",
    "onManaChange",
    "onModalWindow",
    "onExtendedOpcode",
    "onCastSpell",
    "creatureSayCallback",
    "onCreatureAppear",
    "onCreatureDisappear",
    "onCreatureMove",
    "onCreatureSay",
}


def _find_function_definitions(code: str) -> List[Tuple[str, int]]:
    """Find all function definitions in code. Returns (name, line)."""
    defs = []
    for m in _FUNC_DEF_RE.finditer(code):
        name = m.group(1)
        line = code[: m.start()].count("\n") + 1
        defs.append((name, line))
    return defs


def _find_function_references(code: str, func_name: str) -> int:
    """Count how many times a function name appears as a call (not definition)."""
    # Simple name (no dots/colons)
    base_name = func_name.split(".")[-1].split(":")[-1]
    pattern = re.compile(r"\b" + re.escape(base_name) + r"\b")
    count = 0
    for m in pattern.finditer(code):
        # Skip the definition itself
        line_start = code.rfind("\n", 0, m.start()) + 1
        line_end = code.find("\n", m.start())
        if line_end == -1:
            line_end = len(code)
        line_text = code[line_start:line_end]
        if re.match(r"\s*(?:local\s+)?function\s+", line_text):
            continue
        count += 1
    return count


# ---------------------------------------------------------------------------
# Main detector
# ---------------------------------------------------------------------------


def detect_dead_code(directory: str) -> DeadCodeReport:
    """Run the full dead-code analysis on a server directory."""
    scan = scan_directory(directory)
    report = DeadCodeReport()

    lua_files = find_lua_files(directory)
    xml_files = find_xml_files(directory)
    report.total_scripts_scanned = len(lua_files)
    report.total_xml_scanned = len(xml_files)

    # 1) Collect all script references from XMLs
    referenced_scripts: Set[str] = set()  # normalized absolute paths
    xml_registration_files = []
    for xml_name in (
        "actions.xml",
        "movements.xml",
        "talkactions.xml",
        "creaturescripts.xml",
        "globalevents.xml",
    ):
        attr_name = xml_name.replace(".xml", "_xml")
        xml_path = getattr(scan, attr_name, None)
        if xml_path:
            xml_registration_files.append(xml_path)

    for xml_path in xml_registration_files:
        refs = _extract_xml_script_refs(xml_path)
        for script_ref, line_num in refs:
            resolved = _resolve_script_path(xml_path, script_ref, scan)
            if os.path.isfile(resolved):
                referenced_scripts.add(os.path.normpath(resolved).lower())
            else:
                report.broken_xml_refs.append(
                    BrokenXmlRef(
                        xml_file=xml_path,
                        script_ref=script_ref,
                        expected_path=resolved,
                        line=line_num,
                    )
                )

    # 2) Find orphan scripts (Lua in component dirs but not referenced in XML)
    component_dirs = {}
    for attr, category in [
        ("actions_dir", "actions"),
        ("movements_dir", "movements"),
        ("talkactions_dir", "talkactions"),
        ("creaturescripts_dir", "creaturescripts"),
        ("globalevents_dir", "globalevents"),
    ]:
        d = getattr(scan, attr, None)
        if d:
            component_dirs[os.path.normpath(d).lower()] = category

    for filepath in lua_files:
        norm_path = os.path.normpath(filepath).lower()
        # Check if this file is inside a component dir
        for comp_dir, category in component_dirs.items():
            if norm_path.startswith(comp_dir):
                if norm_path not in referenced_scripts:
                    report.orphan_scripts.append(
                        OrphanScript(
                            filepath=filepath,
                            category=category,
                        )
                    )
                break

    # 3) Unused functions (defined but never called anywhere in the project)
    # First, read all code
    all_code_combined = []
    file_defs: List[Tuple[str, str, int]] = []  # (filepath, func_name, line)

    for filepath in lua_files:
        code = read_file_safe(filepath)
        if code is None:
            continue
        all_code_combined.append(code)

        for func_name, line in _find_function_definitions(code):
            file_defs.append((filepath, func_name, line))

    combined = "\n".join(all_code_combined)

    for filepath, func_name, line in file_defs:
        # Skip known callbacks
        base = func_name.split(".")[-1].split(":")[-1]
        if base in _KNOWN_CALLBACKS:
            continue

        ref_count = _find_function_references(combined, func_name)
        if ref_count == 0:
            report.unused_functions.append(
                UnusedFunction(
                    filepath=filepath,
                    function_name=func_name,
                    line=line,
                )
            )

    return report
