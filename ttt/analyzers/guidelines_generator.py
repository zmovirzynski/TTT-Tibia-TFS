"""Generates LLM-ready refactoring guidelines from Lua analysis + dry-run data."""

import os
from datetime import date
from typing import Dict, List, Optional, TYPE_CHECKING

from .lua_oop_analyzer import LuaFileAnalysis, LuaOopIssue

if TYPE_CHECKING:
    from ..report import ConversionReport, FileReport


def _priority(lua: LuaFileAnalysis, fr: Optional["FileReport"]) -> int:
    """Higher = more urgent."""
    score = len(lua.issues) * 2
    if fr:
        if fr.confidence_label in ("LOW", "REVIEW"):
            score += 4
        elif fr.confidence_label == "MEDIUM":
            score += 2
        score += min(fr.ttt_warnings, 5)
        score += min(len(fr.unrecognized_calls), 5)
    return score


class GuidelinesGenerator:
    def generate(
        self,
        lua_analyses: List[LuaFileAnalysis],
        report: Optional["ConversionReport"] = None,
    ) -> str:
        # Index file reports by relative path for quick lookup
        fr_index: Dict[str, "FileReport"] = {}
        if report:
            for fr in report.file_reports:
                rel = (
                    os.path.relpath(fr.source_path, report.input_dir)
                    if report.input_dir
                    else os.path.basename(fr.source_path)
                )
                fr_index[rel] = fr

        # Pair and sort by priority
        pairs = []
        for lua in lua_analyses:
            fr = fr_index.get(lua.file_path)
            pairs.append((lua, fr, _priority(lua, fr)))
        pairs.sort(key=lambda x: -x[2])

        files_with_issues = [p for p in pairs if p[0].issues or (p[1] and (p[1].ttt_warnings or p[1].unrecognized_calls))]
        files_clean = [p for p in pairs if p not in files_with_issues]

        total_lua_issues = sum(len(p[0].issues) for p in pairs)
        total_ttt_warnings = sum((p[1].ttt_warnings if p[1] else 0) for p in pairs)
        total_unrec = sum((len(p[1].unrecognized_calls) if p[1] else 0) for p in pairs)

        conv_info = ""
        if report:
            conv_info = f"Conversion: {report.source_version} → {report.target_version}  \n"

        lines = [
            "# Lua OOP Refactoring Guidelines",
            "",
            f"Generated: {date.today().isoformat()}  ",
            f"{conv_info}Files analyzed: {len(pairs)}  ",
            f"Files needing attention: {len(files_with_issues)}  ",
            f"Lua OOP issues: {total_lua_issues}  ",
            f"TTT review markers: {total_ttt_warnings}  ",
            f"Unrecognized calls: {total_unrec}",
            "",
            "---",
            "",
        ]

        for lua, fr, _ in files_with_issues:
            lines.extend(self._format_file(lua, fr))

        if files_clean:
            lines.append("## Clean files")
            lines.append("")
            lines.append("No issues detected in:")
            lines.append("")
            for lua, fr, _ in files_clean:
                conf = f" · confidence: {fr.confidence_label}" if fr else ""
                lines.append(f"- `{lua.file_path}` ({lua.total_lines} lines{conf})")
            lines.append("")

        return "\n".join(lines)

    def _format_file(
        self,
        lua: LuaFileAnalysis,
        fr: Optional["FileReport"],
    ) -> List[str]:
        # Build priority label
        conf_label = fr.confidence_label if fr else "N/A"
        priority = "HIGH" if conf_label in ("LOW", "REVIEW") else ("MEDIUM" if conf_label == "MEDIUM" else "LOW")
        if lua.issues and priority == "LOW":
            priority = "MEDIUM"

        lines = [
            f"## `{lua.file_path}`  ({lua.total_lines} lines)",
            "",
            f"**Priority: {priority}**"
            + (f" · Confidence: {conf_label}" if fr else ""),
        ]
        if fr and fr.ttt_warnings:
            lines[-1] += f" · {fr.ttt_warnings} TTT marker(s)"
        if fr and fr.unrecognized_calls:
            lines[-1] += f" · {len(fr.unrecognized_calls)} unrecognized call(s)"
        lines.append("")

        if lua.issues:
            lines.append("### Lua OOP Issues")
            lines.append("")
            for i, issue in enumerate(lua.issues, 1):
                lines.append(f"**{i}. {self._label(issue.issue_type)}**")
                lines.append(f"- {issue.description}")
                lines.append(f"- Guideline: {issue.guideline}")
                lines.append("")

        if getattr(lua, "ast_metrics", None):
            lines.extend(self._format_ast_section(lua.ast_metrics))

        if fr:
            if fr.unrecognized_calls:
                lines.append("### Conversion Warnings")
                lines.append("")
                funcs = ", ".join(f"`{f}`" for f in fr.unrecognized_calls[:8])
                if len(fr.unrecognized_calls) > 8:
                    funcs += f" (+{len(fr.unrecognized_calls) - 8} more)"
                lines.append(f"- Unrecognized functions: {funcs}")
                lines.append("  These have no automatic mapping and need manual OOP conversion.")
                lines.append("")
            if fr.ttt_warnings:
                lines.append(
                    f"- {fr.ttt_warnings} line(s) marked with `-- TTT:` require manual review."
                )
                lines.append("")

        lines.append("### Suggested LLM prompt")
        lines.append("")
        topics = [self._label(i.issue_type) for i in lua.issues[:3]]
        if fr and fr.unrecognized_calls:
            topics.append("unrecognized call mapping")
        topics_str = "; ".join(topics) if topics else "review for OOP conversion"
        if getattr(lua, "ast_metrics", None) and lua.ast_metrics.high_complexity_functions:
            fn = lua.ast_metrics.high_complexity_functions[0]
            complexity_hint = (
                f" Focus on `{fn.name}` (cyclomatic={fn.cyclomatic}, nesting={fn.nesting_depth}) first."
            )
        else:
            complexity_hint = ""
        lines.append(
            f"> Refactor `{lua.file_path}` for TFS 1.x/RevScript OOP style: "
            f"{topics_str}. Cache entity objects as locals, use method calls "
            f"instead of global functions, and handle nil player guards.{complexity_hint}"
        )
        lines.append("")
        lines.append("---")
        lines.append("")
        return lines

    def _format_ast_section(self, ast_metrics) -> List[str]:
        """Emit AST metrics block for the LLM prompt."""
        lines = []
        if ast_metrics.function_metrics:
            lines.append("### AST Complexity")
            lines.append("")
            # Show high-complexity functions first, then others up to a total of 5
            high = ast_metrics.high_complexity_functions
            shown = set()
            for fn in high[:5]:
                lines.append(
                    f"- `{fn.name}`: cyclomatic={fn.cyclomatic} ({fn.rating}), "
                    f"nesting={fn.nesting_depth}"
                )
                shown.add(fn.name)
            # Fill remaining slots with other functions
            remaining = 5 - len(shown)
            if remaining > 0:
                for fn in ast_metrics.function_metrics:
                    if fn.name not in shown and remaining > 0:
                        lines.append(
                            f"- `{fn.name}`: cyclomatic={fn.cyclomatic} ({fn.rating}), "
                            f"nesting={fn.nesting_depth}"
                        )
                        shown.add(fn.name)
                        remaining -= 1
            lines.append("")
        if ast_metrics.unused_locals:
            names = ", ".join(f"`{u.name}`" for u in ast_metrics.unused_locals[:6])
            if len(ast_metrics.unused_locals) > 6:
                names += f" (+{len(ast_metrics.unused_locals) - 6} more)"
            lines.append(f"**Unused locals:** {names}")
            lines.append("")
        return lines

    @staticmethod
    def _label(issue_type: str) -> str:
        return {
            "CID_USAGE": "Player/cid → OOP object",
            "OLD_API_CALLS": "Old procedural API calls",
            "NIL_GUARD_PATTERN": "Nil guard migration (isCreature/isPlayer)",
            "STORAGE_KEY_TABLE": "Storage key table",
            "STORAGE_KEY_GLOBALS": "Standalone storage key globals",
            "ADD_EVENT_CID": "addEvent() with creature ID (crash risk)",
            "CONDITION_OBJECT": "Old condition chain (createConditionObject)",
            "COMBAT_CALLS": "Raw combat damage calls",
            "EFFECT_SEQUENCE": "Timed effect sequence via addEvent",
            "RECURSIVE_ADDEVENT": "Self-rescheduling function via addEvent",
            "MULTI_ENTITY": "Multiple entity variables",
            "LARGE_FUNCTIONS": "Large functions",
            "GLOBAL_STATE": "Global state",
        }.get(issue_type, issue_type)
