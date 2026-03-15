"""Formats OOP analysis results as LLM-ready markdown guidelines."""

import os
from datetime import date
from typing import List

from .oop_analyzer import FileAnalysis, OopIssue


class GuidelinesGenerator:
    def generate(self, analyses: List[FileAnalysis], ttt_root: str) -> str:
        files_with_issues = [a for a in analyses if a.issues]
        files_clean = [a for a in analyses if not a.issues]

        total_issues = sum(len(a.issues) for a in files_with_issues)
        today = date.today().isoformat()

        lines = [
            "# OOP Refactoring Guidelines for LLM Assistants",
            "",
            f"Generated: {today}  ",
            f"Files analyzed: {len(analyses)}  ",
            f"Files with issues: {len(files_with_issues)}  ",
            f"Total issues: {total_issues}",
            "",
            "---",
            "",
        ]

        for analysis in files_with_issues:
            lines.extend(self._format_file(analysis))

        if files_clean:
            lines.append("## Clean files")
            lines.append("")
            lines.append("No OOP issues detected in:")
            lines.append("")
            for analysis in files_clean:
                lines.append(f"- `{analysis.file_path}` ({analysis.total_lines} lines)")
            lines.append("")

        return "\n".join(lines)

    def _format_file(self, analysis: FileAnalysis) -> List[str]:
        lines = [
            f"## {analysis.file_path}  ({analysis.total_lines} lines)",
            "",
            "### Issues Found",
            "",
        ]

        for i, issue in enumerate(analysis.issues, 1):
            span = issue.line_end - issue.line_start + 1
            header = (
                f"**{i}. {self._label(issue.issue_type)}: "
                f"`{issue.entity_name}` "
                f"(lines {issue.line_start}–{issue.line_end}, {span} lines)**"
            )
            lines.append(header)
            lines.append(f"- Description: {issue.description}")
            lines.append(f"- Guideline for LLM: {issue.guideline}")
            lines.append("")

        lines.append("### Suggested LLM prompt")
        lines.append("")
        issue_labels = ", ".join(
            f"`{i.entity_name}`" for i in analysis.issues[:5]
        )
        if len(analysis.issues) > 5:
            issue_labels += f" and {len(analysis.issues) - 5} more"
        lines.append(
            f"> Refactor `{analysis.file_path}` following these guidelines: "
            f"address {issue_labels}. "
            "Apply OOP principles — extract helper methods, introduce dataclasses, "
            "reduce parameter lists, and move standalone functions into classes."
        )
        lines.append("")
        lines.append("---")
        lines.append("")

        return lines

    @staticmethod
    def _label(issue_type: str) -> str:
        return {
            "METHOD_TOO_LONG": "Method too long",
            "TOO_MANY_PARAMS": "Too many parameters",
            "DICT_AS_OBJECT": "Dict-as-object pattern",
            "STANDALONE_FUNCTION": "Standalone function outside class",
        }.get(issue_type, issue_type)
