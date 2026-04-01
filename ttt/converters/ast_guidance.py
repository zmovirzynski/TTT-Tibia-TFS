"""AST-assisted guidance — Generates detailed migration guidance from AST analysis.

Enhances the conversion pipeline with scope-aware suggestions,
type safety hints, and pattern-specific recommendations.
"""

from dataclasses import dataclass, field
from typing import Dict, List
import re


@dataclass
class GuidanceEntry:
    """A single guidance recommendation."""

    file: str = ""
    line: int = 0
    severity: str = "info"  # info, warning, action
    category: str = ""  # type_safety, pattern, scope, performance, compat
    title: str = ""
    detail: str = ""
    suggestion: str = ""


@dataclass
class GuidanceReport:
    """Aggregated guidance for a conversion run."""

    entries: List[GuidanceEntry] = field(default_factory=list)

    def add(self, entry: GuidanceEntry) -> None:
        self.entries.append(entry)

    @property
    def by_severity(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self.entries:
            counts[e.severity] = counts.get(e.severity, 0) + 1
        return counts

    @property
    def by_category(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self.entries:
            counts[e.category] = counts.get(e.category, 0) + 1
        return counts

    def to_dict(self) -> Dict:
        return {
            "total": len(self.entries),
            "by_severity": self.by_severity,
            "by_category": self.by_category,
            "entries": [
                {
                    "file": e.file,
                    "line": e.line,
                    "severity": e.severity,
                    "category": e.category,
                    "title": e.title,
                    "detail": e.detail,
                    "suggestion": e.suggestion,
                }
                for e in self.entries
            ],
        }

    def to_text(self) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("  TTT AST-Assisted Guidance Report")
        lines.append("=" * 70)
        lines.append(f"  Total recommendations: {len(self.entries)}")
        for sev, count in sorted(self.by_severity.items()):
            lines.append(f"    {sev}: {count}")
        lines.append("")

        for e in self.entries:
            icon = {"info": "ℹ", "warning": "⚠", "action": "→"}.get(e.severity, "•")
            lines.append(f"  {icon} [{e.category}] {e.title}")
            if e.file:
                loc = f"{e.file}:{e.line}" if e.line else e.file
                lines.append(f"    File: {loc}")
            if e.detail:
                lines.append(f"    {e.detail}")
            if e.suggestion:
                lines.append(f"    Suggestion: {e.suggestion}")
            lines.append("")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analysis functions
# ---------------------------------------------------------------------------


def analyze_converted_code(
    code: str, original: str, filename: str, report: GuidanceReport
) -> None:
    """Analyze converted code and generate guidance entries."""
    _check_nil_safety(code, filename, report)
    _check_deprecated_patterns(code, filename, report)
    _check_object_lifecycle(code, filename, report)
    _check_type_coercion(code, filename, report)
    _check_event_registration(code, filename, report)
    _check_storage_usage(code, original, filename, report)


def _check_nil_safety(code: str, filename: str, report: GuidanceReport) -> None:
    """Detect potential nil access after object construction."""
    # Pattern: Player(x):method() without nil check
    pattern = re.compile(
        r"(Player|Creature|Item|Monster|Npc|Tile|Container)\(([^)]+)\):(\w+)\(",
        re.MULTILINE,
    )
    for match in pattern.finditer(code):
        wrapper = match.group(1)
        arg = match.group(2).strip()
        method = match.group(3)
        line = code[: match.start()].count("\n") + 1

        # Skip if there's a nil check nearby (within 3 lines before)
        context_start = max(0, code.rfind("\n", 0, max(0, match.start() - 200)))
        context = code[context_start : match.start()]
        if f"if not {wrapper}({arg})" in context or f"if {wrapper}({arg})" in context:
            continue

        report.add(
            GuidanceEntry(
                file=filename,
                line=line,
                severity="warning",
                category="type_safety",
                title=f"Potential nil from {wrapper}({arg})",
                detail=f"{wrapper}({arg}):{method}() will error if the object doesn't exist",
                suggestion=f"Add a nil check: local obj = {wrapper}({arg}); if obj then obj:{method}(...) end",
            )
        )


def _check_deprecated_patterns(
    code: str, filename: str, report: GuidanceReport
) -> None:
    """Detect deprecated TFS 1.x patterns that should be updated."""
    deprecations = [
        (
            r"\bgetConfigValue\b",
            "getConfigValue",
            "Use configManager[key] instead of getConfigValue()",
        ),
        (r"\bdoRemoveCreature\b", "doRemoveCreature", "Use creature:remove() instead"),
        (r"\bdoRemoveItem\b", "doRemoveItem", "Use item:remove() instead"),
        (
            r"\bdoPlayerSendTextMessage\b",
            "doPlayerSendTextMessage",
            "Use player:sendTextMessage() instead",
        ),
        (
            r"\baddEvent\b.*\baddEvent\b",
            "Nested addEvent",
            "Consider consolidating nested addEvent calls for clarity",
        ),
    ]
    for pat, name, suggestion in deprecations:
        for match in re.finditer(pat, code):
            line = code[: match.start()].count("\n") + 1
            report.add(
                GuidanceEntry(
                    file=filename,
                    line=line,
                    severity="info",
                    category="compat",
                    title=f"Deprecated pattern: {name}",
                    detail=f"Found {name} which may not work in newer TFS versions",
                    suggestion=suggestion,
                )
            )


def _check_object_lifecycle(code: str, filename: str, report: GuidanceReport) -> None:
    """Detect object references that may go stale across addEvent boundaries."""
    # Pattern: addEvent with a captured player/creature variable
    add_event_pat = re.compile(
        r"addEvent\s*\(\s*function\s*\(\)\s*\n(.*?)\n\s*end", re.DOTALL
    )
    obj_access_pat = re.compile(r"\b(player|creature|target|monster)\b:(\w+)\(")

    for ae_match in add_event_pat.finditer(code):
        body = ae_match.group(1)
        for oa_match in obj_access_pat.finditer(body):
            var_name = oa_match.group(1)
            method = oa_match.group(2)
            line = code[: ae_match.start()].count("\n") + 1
            report.add(
                GuidanceEntry(
                    file=filename,
                    line=line,
                    severity="warning",
                    category="scope",
                    title=f"Stale reference risk in addEvent: {var_name}",
                    detail=f"{var_name}:{method}() inside addEvent — player may have "
                    f"logged out by the time the event fires",
                    suggestion=f"Store {var_name}:getId() before addEvent, then re-fetch "
                    f"with Player({var_name}Id) inside the callback",
                )
            )


def _check_type_coercion(code: str, filename: str, report: GuidanceReport) -> None:
    """Detect potential type coercion issues in converted code."""
    # getVocation():getId() returns number, but some scripts compare to string
    voc_string_pat = re.compile(
        r':getVocation\(\):getId\(\)\s*==\s*["\']', re.MULTILINE
    )
    for match in voc_string_pat.finditer(code):
        line = code[: match.start()].count("\n") + 1
        report.add(
            GuidanceEntry(
                file=filename,
                line=line,
                severity="action",
                category="type_safety",
                title="Vocation ID compared to string",
                detail="getVocation():getId() returns a number but is being compared to a string",
                suggestion="Use numeric comparison: getVocation():getId() == 1",
            )
        )

    # tonumber() on something that's already a number method
    tonumber_pat = re.compile(
        r"tonumber\s*\(\s*\w+:(getLevel|getHealth|getMana|getSoul|getSkillLevel)\(",
        re.MULTILINE,
    )
    for match in tonumber_pat.finditer(code):
        method = match.group(1)
        line = code[: match.start()].count("\n") + 1
        report.add(
            GuidanceEntry(
                file=filename,
                line=line,
                severity="info",
                category="type_safety",
                title=f"Unnecessary tonumber() on :{method}()",
                detail=f":{method}() already returns a number in TFS 1.x",
                suggestion="Remove the tonumber() wrapper",
            )
        )


def _check_event_registration(code: str, filename: str, report: GuidanceReport) -> None:
    """Check for proper RevScript event registration patterns."""
    # File has event handler but no registration
    has_handler = bool(re.search(r"function\s+\w+\.on\w+\(", code))
    has_registration = bool(
        re.search(
            r":(onUse|onSay|onLogin|onLogout|onStepIn|onStepOut|onEquip|onDeEquip|"
            r"onAddItem|onMoveItem|onThink|onHealthChange|onManaChange|"
            r"onPrepareDeath|onDeath|onKill|onStartup|onShutdown|onRecord|"
            r"onExtendedOpcode|onModalWindow|onTextEdit)\s*\(",
            code,
        )
    ) or bool(re.search(r":register\(\)", code))

    if has_handler and not has_registration:
        report.add(
            GuidanceEntry(
                file=filename,
                line=1,
                severity="action",
                category="pattern",
                title="Event handler without RevScript registration",
                detail="This file has event handler functions but no RevScript-style "
                "registration (Action/MoveEvent/TalkAction/etc. + :register())",
                suggestion="Add RevScript registration at the bottom of the file",
            )
        )


def _check_storage_usage(
    code: str, original: str, filename: str, report: GuidanceReport
) -> None:
    """Detect storage key usage patterns that may need attention."""
    # Hard-coded storage keys
    storage_pat = re.compile(
        r":(?:getStorageValue|setStorageValue)\s*\(\s*(\d+)", re.MULTILINE
    )
    keys_found = set()
    for match in storage_pat.finditer(code):
        key = match.group(1)
        keys_found.add(key)

    if len(keys_found) > 5:
        report.add(
            GuidanceEntry(
                file=filename,
                line=1,
                severity="info",
                category="pattern",
                title=f"Many hard-coded storage keys ({len(keys_found)})",
                detail=f"Found {len(keys_found)} different numeric storage keys",
                suggestion="Consider using a storage key constants table for maintainability",
            )
        )
