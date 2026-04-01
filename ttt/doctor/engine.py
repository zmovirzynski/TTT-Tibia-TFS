"""
Doctor engine — Orchestrates health checks + XML validation + health score.

Combines: health_check, xml_validator.
Outputs: text, JSON, HTML.
Health Score: HEALTHY (90-100) / WARNING (60-89) / CRITICAL (0-59)
"""

import json
import os
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

from .health_check import run_health_checks, HealthReport, HealthIssue
from .xml_validator import validate_xml_files, XmlValidationReport

logger = logging.getLogger("ttt")


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DOCTOR_MODULES = ["health_check", "xml_validator"]


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class DoctorReport:
    """Complete doctor report combining health checks + XML validation."""
    directory: str = ""
    health: Optional[HealthReport] = None
    xml_validation: Optional[XmlValidationReport] = None

    @property
    def total_issues(self) -> int:
        total = 0
        if self.health:
            total += self.health.total_issues
        if self.xml_validation:
            total += self.xml_validation.total_issues
        return total

    @property
    def total_errors(self) -> int:
        total = 0
        if self.health:
            total += len(self.health.errors)
        if self.xml_validation:
            total += len(self.xml_validation.errors)
        return total

    @property
    def total_warnings(self) -> int:
        total = 0
        if self.health:
            total += len(self.health.warnings)
        if self.xml_validation:
            total += len(self.xml_validation.warnings)
        return total

    @property
    def total_checks(self) -> int:
        total = 0
        if self.health:
            total += self.health.total_checks_run
        if self.xml_validation:
            total += self.xml_validation.total_files_scanned
        return total

    @property
    def health_score(self) -> int:
        """Calculate health score 0-100."""
        total = self.total_checks
        if total == 0:
            return 100
        # Errors weigh 10 points, warnings weigh 3 points
        penalty = (self.total_errors * 10) + (self.total_warnings * 3)
        score = max(0, 100 - penalty)
        return score

    @property
    def health_rating(self) -> str:
        """HEALTHY / WARNING / CRITICAL."""
        score = self.health_score
        if score >= 90:
            return "HEALTHY"
        elif score >= 60:
            return "WARNING"
        else:
            return "CRITICAL"

    def as_dict(self) -> Dict:
        d = {
            "directory": self.directory,
            "health_score": self.health_score,
            "health_rating": self.health_rating,
            "total_issues": self.total_issues,
            "total_errors": self.total_errors,
            "total_warnings": self.total_warnings,
        }
        if self.health:
            d["health_check"] = self.health.as_dict()
        if self.xml_validation:
            d["xml_validation"] = self.xml_validation.as_dict()
        return d


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class DoctorEngine:
    """Runs all doctor checks on a server directory."""

    def __init__(self, enabled_modules: Optional[List[str]] = None):
        if enabled_modules is None:
            self.enabled = set(DOCTOR_MODULES)
        else:
            self.enabled = set(enabled_modules) & set(DOCTOR_MODULES)

    def diagnose(self, directory: str) -> DoctorReport:
        """Run the full diagnosis."""
        report = DoctorReport(directory=directory)

        if "health_check" in self.enabled:
            logger.info("Running health checks...")
            report.health = run_health_checks(directory)

        if "xml_validator" in self.enabled:
            logger.info("Running XML validator...")
            report.xml_validation = validate_xml_files(directory)

        return report


# ---------------------------------------------------------------------------
# Text formatter
# ---------------------------------------------------------------------------

class _Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"
    WHITE = "\033[37m"


def format_doctor_text(report: DoctorReport, no_color: bool = False,
                        verbose: bool = False, base_dir: str = "") -> str:
    """Format doctor report as colored text for terminal."""
    C = _Colors
    if no_color:
        for attr in dir(C):
            if not attr.startswith("_"):
                setattr(C, attr, "")

    lines = []
    _sep = "=" * 60

    lines.append("")
    lines.append(f"  {C.BOLD}TTT Server Health Check{C.RESET}")
    lines.append(f"  {_sep}")
    lines.append(f"  Directory: {C.CYAN}{report.directory}{C.RESET}")
    lines.append("")

    # --- Health score header ---
    score = report.health_score
    rating = report.health_rating
    if rating == "HEALTHY":
        color = C.GREEN
        icon = "[OK]"
    elif rating == "WARNING":
        color = C.YELLOW
        icon = "[!!]"
    else:
        color = C.RED
        icon = "[XX]"

    lines.append(f"  {C.BOLD}Health Score: {color}{score}/100  {icon} {rating}{C.RESET}")
    lines.append("")

    # --- Errors ---
    all_errors = []
    if report.health:
        all_errors.extend(report.health.errors)
    if report.xml_validation:
        all_errors.extend(report.xml_validation.errors)

    if all_errors:
        lines.append(f"  {C.RED}{C.BOLD}ERRORS ({len(all_errors)}){C.RESET}")
        lines.append(f"  {'-' * 58}")
        for issue in all_errors:
            fp = _rel(issue.filepath if isinstance(issue, HealthIssue) else issue.filepath, base_dir)
            ln = ""
            if hasattr(issue, "line") and issue.line:
                ln = f":L{issue.line}"
            msg = issue.message
            lines.append(f"    {C.RED}[ERR]{C.RESET} {fp}{ln}")
            lines.append(f"          {msg}")
        lines.append("")

    # --- Warnings ---
    all_warnings = []
    if report.health:
        all_warnings.extend(report.health.warnings)
    if report.xml_validation:
        all_warnings.extend(report.xml_validation.warnings)

    if all_warnings:
        lines.append(f"  {C.YELLOW}{C.BOLD}WARNINGS ({len(all_warnings)}){C.RESET}")
        lines.append(f"  {'-' * 58}")
        for issue in all_warnings:
            fp = _rel(issue.filepath if isinstance(issue, HealthIssue) else issue.filepath, base_dir)
            ln = ""
            if hasattr(issue, "line") and issue.line:
                ln = f":L{issue.line}"
            msg = issue.message
            lines.append(f"    {C.YELLOW}[WRN]{C.RESET} {fp}{ln}")
            lines.append(f"          {msg}")
        lines.append("")

    # --- Passed ---
    if not all_errors and not all_warnings:
        lines.append(f"  {C.GREEN}{C.BOLD}No issues found! Server is healthy.{C.RESET}")
        lines.append("")

    # --- Summary ---
    lines.append(f"  {C.BOLD}SUMMARY{C.RESET}")
    lines.append(f"  {'-' * 58}")
    total_files = 0
    if report.health:
        total_files = report.health.total_files_scanned
    elif report.xml_validation:
        total_files = report.xml_validation.total_files_scanned
    lines.append(f"    Files scanned: {total_files}")
    lines.append(f"    Errors:   {C.RED}{report.total_errors}{C.RESET}")
    lines.append(f"    Warnings: {C.YELLOW}{report.total_warnings}{C.RESET}")
    if report.xml_validation:
        lines.append(f"    XML files valid: {C.GREEN}{report.xml_validation.total_files_valid}"
                     f"/{report.xml_validation.total_files_scanned}{C.RESET}")
    lines.append("")

    return "\n".join(lines)


def _rel(filepath: str, base_dir: str) -> str:
    """Get relative path if possible."""
    if base_dir:
        try:
            return os.path.relpath(filepath, base_dir)
        except ValueError:
            pass
    return filepath


# ---------------------------------------------------------------------------
# JSON formatter
# ---------------------------------------------------------------------------

def format_doctor_json(report: DoctorReport) -> str:
    """Format doctor report as JSON."""
    return json.dumps(report.as_dict(), indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# HTML formatter
# ---------------------------------------------------------------------------

def format_doctor_html(report: DoctorReport) -> str:
    """Format doctor report as standalone HTML page."""
    score = report.health_score
    rating = report.health_rating

    if rating == "HEALTHY":
        badge_color = "#28a745"
        badge_icon = "&#10003;"  # checkmark
    elif rating == "WARNING":
        badge_color = "#ffc107"
        badge_icon = "&#9888;"   # warning
    else:
        badge_color = "#dc3545"
        badge_icon = "&#10007;"  # X

    # Collect all issues
    all_issues = []
    if report.health:
        for issue in report.health.issues:
            all_issues.append({
                "severity": issue.severity,
                "check": issue.check_name,
                "file": issue.filepath,
                "line": issue.line,
                "message": issue.message,
            })
    if report.xml_validation:
        for issue in report.xml_validation.issues:
            all_issues.append({
                "severity": issue.severity,
                "check": issue.check_name,
                "file": issue.filepath,
                "line": issue.line,
                "message": issue.message,
            })

    # Build issue rows
    issue_rows = ""
    for iss in all_issues:
        sev_class = "error" if iss["severity"] == "error" else "warning"
        sev_label = "ERR" if iss["severity"] == "error" else "WRN"
        basename = os.path.basename(iss["file"])
        line_str = f":L{iss['line']}" if iss["line"] else ""
        issue_rows += f"""
        <tr class="{sev_class}">
          <td><span class="badge badge-{sev_class}">{sev_label}</span></td>
          <td>{_html_escape(iss['check'])}</td>
          <td>{_html_escape(basename)}{line_str}</td>
          <td>{_html_escape(iss['message'])}</td>
        </tr>"""

    if not issue_rows:
        issue_rows = """
        <tr>
          <td colspan="4" style="text-align:center; color:#28a745; padding:20px;">
            &#10003; No issues found! Server is healthy.
          </td>
        </tr>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TTT Server Health Report</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, monospace;
         background: #1e1e2e; color: #cdd6f4; padding: 20px; }}
  .container {{ max-width: 1000px; margin: 0 auto; }}
  h1 {{ color: #89b4fa; margin-bottom: 5px; }}
  .subtitle {{ color: #6c7086; margin-bottom: 20px; }}
  .score-card {{ background: #313244; border-radius: 12px; padding: 30px;
                 text-align: center; margin-bottom: 20px; }}
  .score-number {{ font-size: 64px; font-weight: bold; color: {badge_color}; }}
  .score-label {{ font-size: 24px; color: {badge_color}; margin-top: 5px; }}
  .stats {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px;
            margin-bottom: 20px; }}
  .stat-box {{ background: #313244; border-radius: 8px; padding: 15px;
               text-align: center; }}
  .stat-value {{ font-size: 28px; font-weight: bold; }}
  .stat-label {{ color: #6c7086; font-size: 12px; text-transform: uppercase; }}
  .stat-error .stat-value {{ color: #f38ba8; }}
  .stat-warning .stat-value {{ color: #fab387; }}
  .stat-ok .stat-value {{ color: #a6e3a1; }}
  table {{ width: 100%; border-collapse: collapse; background: #313244;
           border-radius: 8px; overflow: hidden; }}
  th {{ background: #45475a; text-align: left; padding: 10px 12px;
       color: #89b4fa; font-size: 13px; text-transform: uppercase; }}
  td {{ padding: 8px 12px; border-bottom: 1px solid #45475a; font-size: 13px; }}
  .badge {{ padding: 2px 8px; border-radius: 4px; font-weight: bold;
            font-size: 11px; color: #1e1e2e; }}
  .badge-error {{ background: #f38ba8; }}
  .badge-warning {{ background: #fab387; }}
  tr.error td {{ border-left: 3px solid #f38ba8; }}
  tr.warning td {{ border-left: 3px solid #fab387; }}
</style>
</head>
<body>
<div class="container">
  <h1>{badge_icon} TTT Server Health Report</h1>
  <p class="subtitle">Directory: {_html_escape(report.directory)}</p>

  <div class="score-card">
    <div class="score-number">{score}/100</div>
    <div class="score-label">{rating}</div>
  </div>

  <div class="stats">
    <div class="stat-box stat-error">
      <div class="stat-value">{report.total_errors}</div>
      <div class="stat-label">Errors</div>
    </div>
    <div class="stat-box stat-warning">
      <div class="stat-value">{report.total_warnings}</div>
      <div class="stat-label">Warnings</div>
    </div>
    <div class="stat-box stat-ok">
      <div class="stat-value">{report.xml_validation.total_files_valid if report.xml_validation else 0}</div>
      <div class="stat-label">XML Valid</div>
    </div>
  </div>

  <table>
    <thead>
      <tr>
        <th>Sev</th>
        <th>Check</th>
        <th>File</th>
        <th>Message</th>
      </tr>
    </thead>
    <tbody>
      {issue_rows}
    </tbody>
  </table>
</div>
</body>
</html>"""

    return html


def _html_escape(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
