"""
Lint reporter — Formats lint results for output.

Supports:
  - Text (terminal, with colors)
  - JSON
  - HTML
"""

import json
import os
from typing import List

from .engine import LintReport
from .rules import LintSeverity


# ---------------------------------------------------------------------------
# ANSI color helpers
# ---------------------------------------------------------------------------


class Colors:
    """ANSI color codes for terminal output."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    MAGENTA = "\033[35m"
    WHITE = "\033[37m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"


def _severity_color(severity: LintSeverity) -> str:
    return {
        LintSeverity.ERROR: Colors.RED,
        LintSeverity.WARNING: Colors.YELLOW,
        LintSeverity.INFO: Colors.CYAN,
        LintSeverity.HINT: Colors.DIM,
    }.get(severity, Colors.WHITE)


def _severity_icon(severity: LintSeverity) -> str:
    return {
        LintSeverity.ERROR: "✗",
        LintSeverity.WARNING: "⚠",
        LintSeverity.INFO: "ℹ",
        LintSeverity.HINT: "·",
    }.get(severity, " ")


def _score_color(score: int) -> str:
    if score >= 90:
        return Colors.GREEN
    elif score >= 70:
        return Colors.YELLOW
    else:
        return Colors.RED


def _score_label(score: int) -> str:
    if score >= 90:
        return "EXCELLENT"
    elif score >= 80:
        return "GOOD"
    elif score >= 70:
        return "ACCEPTABLE"
    elif score >= 50:
        return "NEEDS IMPROVEMENT"
    else:
        return "POOR"


# ---------------------------------------------------------------------------
# Text Reporter
# ---------------------------------------------------------------------------


def format_text(
    report: LintReport,
    base_dir: str = "",
    use_colors: bool = True,
    verbose: bool = False,
) -> str:
    """Format lint report as readable text for terminal output."""
    lines: List[str] = []
    c = (
        Colors
        if use_colors
        else type(
            "NoColors", (), {k: "" for k in dir(Colors) if not k.startswith("_")}
        )()
    )

    if not report.files:
        lines.append(f"\n{c.DIM}No files to lint.{c.RESET}")
        return "\n".join(lines)

    lines.append("")

    # Per-file results
    for file_result in report.files:
        if not file_result.issues and not verbose:
            continue

        # File path header
        rel_path = (
            os.path.relpath(file_result.filepath, base_dir)
            if base_dir
            else file_result.filepath
        )
        lines.append(f"{c.BOLD}{c.WHITE}{rel_path}{c.RESET}")

        if file_result.error:
            lines.append(f"  {c.RED}ERROR: {file_result.error}{c.RESET}")
            lines.append("")
            continue

        if not file_result.issues:
            lines.append(f"  {c.GREEN}✓ No issues{c.RESET}")
            lines.append("")
            continue

        # Issues
        for issue in file_result.issues:
            sev_col = _severity_color(issue.severity) if use_colors else ""
            icon = _severity_icon(issue.severity)
            sev_str = issue.severity.value
            loc = f"L{issue.line}" if issue.line > 0 else "   "
            fix_mark = f" {c.DIM}[fixable]{c.RESET}" if issue.fixable else ""

            lines.append(
                f"  {c.DIM}{loc:<5s}{c.RESET} "
                f"{sev_col}{icon} {sev_str:<8s}{c.RESET} "
                f"{c.DIM}{issue.rule_id:<28s}{c.RESET} "
                f"{issue.message}{fix_mark}"
            )

        # File score
        sc = file_result.score
        sc_col = _score_color(sc) if use_colors else ""
        sc_label = _score_label(sc)
        lines.append(
            f"\n  {c.BOLD}Score: {sc_col}{sc}/100{c.RESET}  {sc_col}{sc_label}{c.RESET}"
        )
        lines.append("")

    # Summary
    lines.append(f"{c.BOLD}{'═' * 60}{c.RESET}")
    lines.append(f"{c.BOLD}Summary{c.RESET}")
    lines.append(f"{'─' * 60}")

    total_files = len(report.files)
    files_ok = total_files - report.files_with_issues
    avg_score = report.average_score
    grade = report.overall_grade
    grade_col = _score_color(int(avg_score)) if use_colors else ""

    lines.append(f"  Files scanned:    {c.BOLD}{total_files}{c.RESET}")
    lines.append(f"  Files with issues:{c.BOLD} {report.files_with_issues}{c.RESET}")
    lines.append(f"  Clean files:      {c.GREEN}{files_ok}{c.RESET}")
    lines.append("")

    if report.total_errors > 0:
        lines.append(f"  {c.RED}✗ Errors:   {report.total_errors}{c.RESET}")
    if report.total_warnings > 0:
        lines.append(f"  {c.YELLOW}⚠ Warnings: {report.total_warnings}{c.RESET}")
    if report.total_infos > 0:
        lines.append(f"  {c.CYAN}ℹ Info:      {report.total_infos}{c.RESET}")

    lines.append(f"  Total issues:     {c.BOLD}{report.total_issues}{c.RESET}")

    if report.total_fixable > 0:
        lines.append(
            f"  Auto-fixable:     {c.GREEN}{report.total_fixable}{c.RESET}"
            f"  {c.DIM}(run 'ttt fix' to auto-correct){c.RESET}"
        )

    lines.append("")
    lines.append(
        f"  Average Score:    {grade_col}{c.BOLD}{avg_score:.0f}/100{c.RESET}"
        f"  Grade: {grade_col}{c.BOLD}{grade}{c.RESET}"
    )
    lines.append(f"{'═' * 60}")
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON Reporter
# ---------------------------------------------------------------------------


def format_json(report: LintReport, base_dir: str = "") -> str:
    """Format lint report as JSON."""
    data = {
        "summary": {
            "totalFiles": len(report.files),
            "filesWithIssues": report.files_with_issues,
            "totalIssues": report.total_issues,
            "errors": report.total_errors,
            "warnings": report.total_warnings,
            "infos": report.total_infos,
            "fixable": report.total_fixable,
            "averageScore": round(report.average_score, 1),
            "grade": report.overall_grade,
        },
        "rulesUsed": report.rules_used,
        "files": [],
    }

    for file_result in report.files:
        rel_path = (
            os.path.relpath(file_result.filepath, base_dir)
            if base_dir
            else file_result.filepath
        )
        file_data = {
            "path": rel_path.replace("\\", "/"),
            "score": file_result.score,
            "error": file_result.error,
            "issues": [
                {
                    "line": issue.line,
                    "column": issue.column,
                    "severity": issue.severity.value,
                    "ruleId": issue.rule_id,
                    "message": issue.message,
                    "suggestion": issue.suggestion,
                    "fixable": issue.fixable,
                }
                for issue in file_result.issues
            ],
        }
        data["files"].append(file_data)

    return json.dumps(data, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# HTML Reporter
# ---------------------------------------------------------------------------


def format_html(report: LintReport, base_dir: str = "") -> str:
    """Format lint report as a standalone HTML page."""
    avg_score = report.average_score
    grade = report.overall_grade

    html_parts = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="UTF-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">',
        "<title>TTT Lint Report</title>",
        "<style>",
        _html_css(),
        "</style>",
        "</head>",
        "<body>",
        '<div class="container">',
        "<h1>TTT Lint Report</h1>",
        '<div class="summary">',
        f'  <div class="score-circle score-{_score_class(avg_score)}">',
        f'    <span class="score-value">{avg_score:.0f}</span>',
        f'    <span class="score-label">Grade {grade}</span>',
        "  </div>",
        '  <div class="stats">',
        f'    <div class="stat"><span class="stat-num">{len(report.files)}</span> files scanned</div>',
        f'    <div class="stat"><span class="stat-num">{report.files_with_issues}</span> files with issues</div>',
        f'    <div class="stat"><span class="stat-num">{report.total_issues}</span> total issues</div>',
        f'    <div class="stat errors"><span class="stat-num">{report.total_errors}</span> errors</div>',
        f'    <div class="stat warnings"><span class="stat-num">{report.total_warnings}</span> warnings</div>',
        f'    <div class="stat infos"><span class="stat-num">{report.total_infos}</span> info</div>',
        f'    <div class="stat fixable"><span class="stat-num">{report.total_fixable}</span> auto-fixable</div>',
        "  </div>",
        "</div>",
    ]

    for file_result in report.files:
        if not file_result.issues:
            continue

        rel_path = (
            os.path.relpath(file_result.filepath, base_dir)
            if base_dir
            else file_result.filepath
        )
        sc = file_result.score
        sc_class = _score_class(sc)

        html_parts.append('<div class="file">')
        html_parts.append('  <div class="file-header">')
        html_parts.append(
            f'    <span class="file-name">{_html_escape(rel_path)}</span>'
        )
        html_parts.append(
            f'    <span class="file-score score-{sc_class}">{sc}/100</span>'
        )
        html_parts.append("  </div>")
        html_parts.append('  <table class="issues">')
        html_parts.append(
            "    <tr><th>Line</th><th>Severity</th><th>Rule</th><th>Message</th></tr>"
        )

        for issue in file_result.issues:
            sev_class = issue.severity.value.lower()
            fix = ' <span class="fixable">[fixable]</span>' if issue.fixable else ""
            html_parts.append(
                f'    <tr class="issue {sev_class}">'
                f"<td>{issue.line}</td>"
                f'<td><span class="badge {sev_class}">{issue.severity.value}</span></td>'
                f"<td>{_html_escape(issue.rule_id)}</td>"
                f"<td>{_html_escape(issue.message)}{fix}</td>"
                f"</tr>"
            )

        html_parts.append("  </table>")
        html_parts.append("</div>")

    html_parts.extend(
        [
            '<div class="footer">Generated by TTT Linter</div>',
            "</div>",
            "</body>",
            "</html>",
        ]
    )

    return "\n".join(html_parts)


def _score_class(score: int) -> str:
    if score >= 90:
        return "high"
    elif score >= 70:
        return "medium"
    else:
        return "low"


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _html_css() -> str:
    return """
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; background: #1a1a2e; color: #e0e0e0; padding: 2rem; }
.container { max-width: 1000px; margin: 0 auto; }
h1 { color: #00d4ff; margin-bottom: 1.5rem; font-size: 1.8rem; }
.summary { display: flex; gap: 2rem; margin-bottom: 2rem; padding: 1.5rem; background: #16213e; border-radius: 8px; border: 1px solid #0f3460; }
.score-circle { width: 100px; height: 100px; border-radius: 50%; display: flex; flex-direction: column; align-items: center; justify-content: center; font-weight: bold; }
.score-circle.score-high { background: #0a3d2a; border: 3px solid #00ff88; color: #00ff88; }
.score-circle.score-medium { background: #3d3a0a; border: 3px solid #ffdd00; color: #ffdd00; }
.score-circle.score-low { background: #3d0a0a; border: 3px solid #ff4444; color: #ff4444; }
.score-value { font-size: 1.8rem; }
.score-label { font-size: 0.7rem; }
.stats { display: flex; flex-wrap: wrap; gap: 1rem; align-items: center; }
.stat { background: #0f3460; padding: 0.5rem 1rem; border-radius: 4px; font-size: 0.9rem; }
.stat-num { font-weight: bold; color: #00d4ff; }
.stat.errors .stat-num { color: #ff4444; }
.stat.warnings .stat-num { color: #ffdd00; }
.stat.infos .stat-num { color: #00bcd4; }
.stat.fixable .stat-num { color: #00ff88; }
.file { margin-bottom: 1.5rem; background: #16213e; border-radius: 8px; border: 1px solid #0f3460; overflow: hidden; }
.file-header { display: flex; justify-content: space-between; align-items: center; padding: 0.8rem 1rem; background: #0f3460; }
.file-name { font-weight: bold; color: #e0e0e0; }
.file-score { font-weight: bold; padding: 2px 8px; border-radius: 4px; font-size: 0.85rem; }
.file-score.score-high { color: #00ff88; }
.file-score.score-medium { color: #ffdd00; }
.file-score.score-low { color: #ff4444; }
.issues { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
.issues th { text-align: left; padding: 0.5rem 0.8rem; background: #1a1a2e; color: #888; font-weight: normal; }
.issues td { padding: 0.4rem 0.8rem; border-top: 1px solid #0f3460; }
.badge { padding: 1px 6px; border-radius: 3px; font-size: 0.75rem; font-weight: bold; }
.badge.error { background: #3d0a0a; color: #ff4444; }
.badge.warning { background: #3d3a0a; color: #ffdd00; }
.badge.info { background: #0a2d3d; color: #00bcd4; }
.badge.hint { background: #2a2a2a; color: #888; }
.fixable { color: #00ff88; font-size: 0.75rem; margin-left: 4px; }
.footer { text-align: center; color: #555; margin-top: 2rem; font-size: 0.8rem; }
"""
