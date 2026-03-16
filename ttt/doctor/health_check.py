"""
Health check rules for OTServ servers.

Each check is a function that takes a directory and returns a list of HealthIssue.
Checks cover:
  - Lua syntax errors
  - Broken XML references (script not found)
  - Conflicting item IDs in actions/movements
  - Duplicate event registrations
  - NPC keyword duplicates
  - Invalid callback signatures
"""

import os
import re
import xml.etree.ElementTree as ET
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Set, Tuple

from ..utils import read_file_safe, find_lua_files, find_xml_files
from ..mappings.signatures import SIGNATURE_MAP


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class HealthIssue:
    """A single issue found by a health check."""
    severity: str   # "error", "warning"
    check_name: str  # e.g. "syntax-error", "broken-xml-ref"
    filepath: str
    line: int = 0
    message: str = ""

    def as_dict(self) -> Dict:
        return {
            "severity": self.severity,
            "check_name": self.check_name,
            "filepath": self.filepath,
            "line": self.line,
            "message": self.message,
        }


@dataclass
class HealthReport:
    """Aggregated health check results."""
    issues: List[HealthIssue] = field(default_factory=list)
    total_checks_run: int = 0
    total_files_scanned: int = 0

    @property
    def errors(self) -> List[HealthIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> List[HealthIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def total_issues(self) -> int:
        return len(self.issues)

    @property
    def total_passed(self) -> int:
        return max(0, self.total_checks_run - self.total_issues)

    def as_dict(self) -> Dict:
        return {
            "issues": [i.as_dict() for i in self.issues],
            "total_checks_run": self.total_checks_run,
            "total_files_scanned": self.total_files_scanned,
            "total_issues": self.total_issues,
            "total_errors": len(self.errors),
            "total_warnings": len(self.warnings),
        }


# ---------------------------------------------------------------------------
# Check: Lua syntax errors
# ---------------------------------------------------------------------------

# Patterns that indicate clear Lua syntax errors
_SYNTAX_PATTERNS = [
    # Unmatched blocks — we count openers/closers
    # Mismatched quotes are harder; we just look for obviously broken patterns
    (r'(?:^|\s)function\s+\w+\s*\([^)]*$', "Possible unterminated function declaration"),
    (r'then\s*$\n\s*$\n\s*end\b', None),  # skip — valid
]

# We use a bracket/block-matching approach for real syntax checks
_BLOCK_OPENERS = re.compile(
    r'\b(?:function|if|for|while|repeat)\b', re.MULTILINE
)
_BLOCK_CLOSERS_END = re.compile(r'\bend\b', re.MULTILINE)
_BLOCK_CLOSERS_UNTIL = re.compile(r'\buntil\b', re.MULTILINE)


def _check_lua_syntax(directory: str) -> List[HealthIssue]:
    """Check Lua files for basic syntax errors (bracket/block mismatches)."""
    issues = []
    lua_files = find_lua_files(directory)

    for filepath in lua_files:
        code = read_file_safe(filepath)
        if code is None:
            continue

        # Strip comments and strings for accurate counting
        cleaned = _strip_comments_and_strings(code)

        # Count block openers vs closers
        openers = len(_BLOCK_OPENERS.findall(cleaned))
        closers_end = len(_BLOCK_CLOSERS_END.findall(cleaned))
        closers_until = len(_BLOCK_CLOSERS_UNTIL.findall(cleaned))
        closers = closers_end + closers_until

        if openers > closers:
            diff = openers - closers
            issues.append(HealthIssue(
                severity="error",
                check_name="syntax-error",
                filepath=filepath,
                message=f"Missing {diff} 'end' statement(s) — {openers} blocks opened, {closers} closed",
            ))
        elif closers > openers:
            diff = closers - openers
            issues.append(HealthIssue(
                severity="error",
                check_name="syntax-error",
                filepath=filepath,
                message=f"Extra {diff} 'end' statement(s) — {openers} blocks opened, {closers} closed",
            ))

        # Check parentheses balance
        parens_open = cleaned.count("(")
        parens_close = cleaned.count(")")
        if parens_open != parens_close:
            issues.append(HealthIssue(
                severity="error",
                check_name="syntax-error",
                filepath=filepath,
                message=f"Unbalanced parentheses: {parens_open} '(' vs {parens_close} ')'",
            ))

    return issues


def _strip_comments_and_strings(code: str) -> str:
    """Remove Lua comments and string literals for analysis."""
    result = []
    i = 0
    length = len(code)
    while i < length:
        # Long comment: --[[ ... ]]
        if code[i:i+4] == '--[[':
            end = code.find(']]', i + 4)
            if end == -1:
                break
            i = end + 2
            continue
        # Long comment: --[=[ ... ]=]
        if code[i:i+3] == '--[' and i + 3 < length and code[i+3] == '=':
            j = i + 3
            while j < length and code[j] == '=':
                j += 1
            if j < length and code[j] == '[':
                eq_count = j - i - 3
                close_tag = ']' + '=' * eq_count + ']'
                end = code.find(close_tag, j + 1)
                if end == -1:
                    break
                i = end + len(close_tag)
                continue
        # Single-line comment
        if code[i:i+2] == '--':
            nl = code.find('\n', i)
            if nl == -1:
                break
            result.append('\n')
            i = nl + 1
            continue
        # Long string [[ ... ]]
        if code[i:i+2] == '[[' and (i == 0 or code[i-1] not in ('-',)):
            end = code.find(']]', i + 2)
            if end != -1:
                i = end + 2
                continue
        # String literal
        if code[i] in ('"', "'"):
            quote = code[i]
            i += 1
            while i < length:
                if code[i] == '\\':
                    i += 2
                    continue
                if code[i] == quote:
                    i += 1
                    break
                i += 1
            continue
        result.append(code[i])
        i += 1
    return ''.join(result)


# ---------------------------------------------------------------------------
# Check: Broken XML references
# ---------------------------------------------------------------------------

def _check_broken_xml_refs(directory: str) -> List[HealthIssue]:
    """Check for XML entries that reference non-existent scripts."""
    issues = []
    xml_files = find_xml_files(directory)

    for xml_path in xml_files:
        content = read_file_safe(xml_path)
        if not content:
            continue

        xml_dir = os.path.dirname(xml_path)
        scripts_dir = os.path.join(xml_dir, "scripts")

        for i, line in enumerate(content.split("\n"), start=1):
            m = re.search(r'script\s*=\s*"([^"]+)"', line, re.IGNORECASE)
            if m:
                script_ref = m.group(1)
                # Try resolving the script path
                candidates = [
                    os.path.join(xml_dir, script_ref),
                    os.path.join(scripts_dir, script_ref),
                    os.path.join(xml_dir, "scripts", script_ref),
                ]
                found = any(os.path.isfile(c) for c in candidates)
                if not found:
                    issues.append(HealthIssue(
                        severity="error",
                        check_name="broken-xml-ref",
                        filepath=xml_path,
                        line=i,
                        message=f"Script '{script_ref}' not found",
                    ))

    return issues


# ---------------------------------------------------------------------------
# Check: Conflicting item IDs (actions/movements)
# ---------------------------------------------------------------------------

def _extract_registrations(xml_path: str, tag: str, id_attrs: List[str]
                            ) -> List[Tuple[str, str, int, str]]:
    """Extract (attr_name, id_value, line, script) tuples from XML."""
    results = []
    content = read_file_safe(xml_path)
    if not content:
        return results

    for i, line in enumerate(content.split("\n"), start=1):
        # Quick check if this line has the tag
        if f"<{tag}" not in line.lower() and f"< {tag}" not in line.lower():
            continue
        for attr in id_attrs:
            # Match itemid="123" or fromid="100" toid="200"
            m = re.search(rf'{attr}\s*=\s*"([^"]+)"', line, re.IGNORECASE)
            if m:
                val = m.group(1)
                # Extract script attr from same line
                sm = re.search(r'script\s*=\s*"([^"]+)"', line, re.IGNORECASE)
                script = sm.group(1) if sm else ""
                results.append((attr, val, i, script))

    return results


def _check_conflicting_ids(directory: str) -> List[HealthIssue]:
    """Check for duplicate item IDs in actions.xml and movements.xml."""
    issues = []

    # Scan for all XML files that contain action or movement registrations
    xml_files = find_xml_files(directory)

    # Track registrations: (reg_type, id_value) -> [(xml_path, line, script)]
    registry: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)

    for xml_path in xml_files:
        basename = os.path.basename(xml_path).lower()

        if "actions" in basename or "action" in basename:
            regs = _extract_registrations(xml_path, "action",
                                           ["itemid", "fromid", "actionid", "uniqueid"])
            for attr, val, line, script in regs:
                key = f"action-{attr}:{val}"
                registry[key].append((xml_path, line, script))

        if "movements" in basename or "movement" in basename:
            regs = _extract_registrations(xml_path, "movevent",
                                           ["itemid", "fromid", "actionid", "uniqueid", "tileitem"])
            for attr, val, line, script in regs:
                key = f"movement-{attr}:{val}"
                registry[key].append((xml_path, line, script))

    for key, entries in registry.items():
        if len(entries) > 1:
            reg_type, id_val = key.split(":", 1)
            files_str = ", ".join(
                f"{os.path.basename(p)}:L{ln}" for p, ln, _ in entries
            )
            for xml_path, line, script in entries:
                issues.append(HealthIssue(
                    severity="error",
                    check_name="conflicting-id",
                    filepath=xml_path,
                    line=line,
                    message=f"Duplicate {reg_type} ID {id_val} — also in: {files_str}",
                ))

    return issues


# ---------------------------------------------------------------------------
# Check: Duplicate event registrations
# ---------------------------------------------------------------------------

def _check_duplicate_events(directory: str) -> List[HealthIssue]:
    """Check for duplicate event names in creaturescripts and talkactions."""
    issues = []
    xml_files = find_xml_files(directory)

    # Talkaction keywords
    keywords: Dict[str, List[Tuple[str, int, str]]] = defaultdict(list)
    # CreatureScript event names
    event_names: Dict[str, List[Tuple[str, int]]] = defaultdict(list)
    # GlobalEvent names
    global_names: Dict[str, List[Tuple[str, int]]] = defaultdict(list)

    for xml_path in xml_files:
        content = read_file_safe(xml_path)
        if not content:
            continue
        basename = os.path.basename(xml_path).lower()

        for i, line in enumerate(content.split("\n"), start=1):
            # Talkaction keywords
            if "talkaction" in basename:
                m = re.search(r'words\s*=\s*"([^"]+)"', line, re.IGNORECASE)
                if m:
                    word = m.group(1).lower()
                    sm = re.search(r'script\s*=\s*"([^"]+)"', line, re.IGNORECASE)
                    script = sm.group(1) if sm else ""
                    keywords[word].append((xml_path, i, script))

            # CreatureScript event names
            if "creaturescript" in basename:
                m = re.search(r'name\s*=\s*"([^"]+)"', line, re.IGNORECASE)
                if m and "<event" in line.lower():
                    name = m.group(1)
                    event_names[name].append((xml_path, i))

            # GlobalEvent names
            if "globalevent" in basename:
                m = re.search(r'name\s*=\s*"([^"]+)"', line, re.IGNORECASE)
                if m and "<globalevent" in line.lower():
                    name = m.group(1)
                    global_names[name].append((xml_path, i))

    for word, entries in keywords.items():
        if len(entries) > 1:
            for xml_path, line, script in entries:
                issues.append(HealthIssue(
                    severity="error",
                    check_name="duplicate-event",
                    filepath=xml_path,
                    line=line,
                    message=f"Duplicate talkaction keyword '{word}'",
                ))

    for name, entries in event_names.items():
        if len(entries) > 1:
            for xml_path, line in entries:
                issues.append(HealthIssue(
                    severity="warning",
                    check_name="duplicate-event",
                    filepath=xml_path,
                    line=line,
                    message=f"Duplicate creature event name '{name}'",
                ))

    for name, entries in global_names.items():
        if len(entries) > 1:
            for xml_path, line in entries:
                issues.append(HealthIssue(
                    severity="warning",
                    check_name="duplicate-event",
                    filepath=xml_path,
                    line=line,
                    message=f"Duplicate global event name '{name}'",
                ))

    return issues


# ---------------------------------------------------------------------------
# Check: NPC keyword duplicates
# ---------------------------------------------------------------------------

def _check_npc_keywords(directory: str) -> List[HealthIssue]:
    """Check for duplicate keywords in NPC scripts."""
    issues = []

    # Find NPC Lua files
    npc_dirs = []
    for root, dirs, files in os.walk(directory):
        for d in dirs:
            if d.lower() == "npc":
                npc_path = os.path.join(root, d)
                scripts_path = os.path.join(npc_path, "scripts")
                if os.path.isdir(scripts_path):
                    npc_dirs.append(scripts_path)
                npc_dirs.append(npc_path)

    # Pattern to find msgcontains or keywords
    keyword_pattern = re.compile(
        r'msgcontains\s*\(\s*msg\s*,\s*["\']([^"\']+)["\']\s*\)',
        re.IGNORECASE
    )

    for npc_dir in npc_dirs:
        for filepath in find_lua_files(npc_dir):
            code = read_file_safe(filepath)
            if not code:
                continue

            keywords: Dict[str, List[int]] = defaultdict(list)
            for i, line in enumerate(code.split("\n"), start=1):
                for m in keyword_pattern.finditer(line):
                    kw = m.group(1).lower()
                    keywords[kw].append(i)

            for kw, lines in keywords.items():
                if len(lines) > 1:
                    lines_str = ", ".join(f"L{l}" for l in lines)
                    issues.append(HealthIssue(
                        severity="warning",
                        check_name="npc-duplicate-keyword",
                        filepath=filepath,
                        line=lines[0],
                        message=f"NPC keyword '{kw}' handled multiple times ({lines_str})",
                    ))

    return issues


# ---------------------------------------------------------------------------
# Check: Invalid callback signatures
# ---------------------------------------------------------------------------

def _check_callback_signatures(directory: str) -> List[HealthIssue]:
    """Check for callbacks with wrong number of parameters."""
    issues = []
    lua_files = find_lua_files(directory)

    # Build a set of known callback names and their expected param counts
    callback_info: Dict[str, Tuple[int, int]] = {}  # name -> (min_params, max_params)
    for cb_name, (old_sig, new_sig) in SIGNATURE_MAP.items():
        old_count = len(old_sig["params"])
        new_count = len(new_sig["params"])
        min_p = min(old_count, new_count)
        max_p = max(old_count, new_count)
        # Also consider alt_params
        if "alt_params" in old_sig:
            for alt in old_sig["alt_params"]:
                min_p = min(min_p, len(alt))
                max_p = max(max_p, len(alt))
        callback_info[cb_name] = (min_p, max_p)

    func_pattern = re.compile(
        r'function\s+(?:\w+[.:])?(\w+)\s*\(([^)]*)\)',
        re.MULTILINE
    )

    for filepath in lua_files:
        code = read_file_safe(filepath)
        if not code:
            continue

        for m in func_pattern.finditer(code):
            func_name = m.group(1)
            params_str = m.group(2).strip()

            if func_name not in callback_info:
                continue

            if params_str:
                params = [p.strip() for p in params_str.split(",") if p.strip()]
            else:
                params = []

            min_p, max_p = callback_info[func_name]

            if len(params) < min_p:
                # Find line number
                line_num = code[:m.start()].count("\n") + 1
                issues.append(HealthIssue(
                    severity="warning",
                    check_name="invalid-callback",
                    filepath=filepath,
                    line=line_num,
                    message=f"Callback '{func_name}' has {len(params)} params, "
                            f"expected at least {min_p}",
                ))
            elif len(params) > max_p:
                line_num = code[:m.start()].count("\n") + 1
                issues.append(HealthIssue(
                    severity="warning",
                    check_name="invalid-callback",
                    filepath=filepath,
                    line=line_num,
                    message=f"Callback '{func_name}' has {len(params)} params, "
                            f"expected at most {max_p}",
                ))

    return issues


# ---------------------------------------------------------------------------
# Registry of all checks
# ---------------------------------------------------------------------------

# Each check: (name, description, function)
HEALTH_CHECKS: List[Tuple[str, str, Callable[[str], List[HealthIssue]]]] = [
    ("syntax-error", "Lua syntax errors (block/bracket mismatch)", _check_lua_syntax),
    ("broken-xml-ref", "XML references to non-existent scripts", _check_broken_xml_refs),
    ("conflicting-id", "Duplicate item IDs in actions/movements", _check_conflicting_ids),
    ("duplicate-event", "Duplicate event registrations", _check_duplicate_events),
    ("npc-duplicate-keyword", "NPC keyword duplicates", _check_npc_keywords),
    ("invalid-callback", "Invalid callback signatures", _check_callback_signatures),
]


def run_health_checks(directory: str,
                       enabled_checks: Optional[Set[str]] = None
                       ) -> HealthReport:
    """Run all (or selected) health checks on a server directory."""
    report = HealthReport()

    lua_files = find_lua_files(directory)
    xml_files = find_xml_files(directory)
    report.total_files_scanned = len(lua_files) + len(xml_files)

    for check_name, _, check_fn in HEALTH_CHECKS:
        if enabled_checks and check_name not in enabled_checks:
            continue

        found = check_fn(directory)
        report.issues.extend(found)
        # Count each file as one check per check type
        report.total_checks_run += report.total_files_scanned

    report.issues.sort(key=lambda i: (
        0 if i.severity == "error" else 1,
        i.filepath,
        i.line,
    ))

    return report
