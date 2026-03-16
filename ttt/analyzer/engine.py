"""
Analyze engine — Orchestrates all analyzer modules and produces reports.

Combines: stats, dead_code, duplicates, storage_scanner, item_usage, complexity.
Outputs: text, JSON, HTML.
"""

import json
import os
import sys
import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from .stats import collect_stats, ServerStats
from .dead_code import detect_dead_code, DeadCodeReport
from .duplicates import detect_duplicates, DuplicateReport
from .storage_scanner import scan_storage, StorageReport
from .item_usage import scan_item_usage, ItemUsageReport
from .complexity import analyze_complexity, ComplexityReport

logger = logging.getLogger("ttt")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

ANALYZER_MODULES = [
    "stats",
    "dead_code",
    "duplicates",
    "storage",
    "item_usage",
    "complexity",
]


@dataclass
class AnalysisReport:
    """Complete analysis report combining all modules."""
    directory: str = ""
    stats: Optional[ServerStats] = None
    dead_code: Optional[DeadCodeReport] = None
    duplicates: Optional[DuplicateReport] = None
    storage: Optional[StorageReport] = None
    item_usage: Optional[ItemUsageReport] = None
    complexity: Optional[ComplexityReport] = None

    @property
    def total_issues(self) -> int:
        total = 0
        if self.dead_code:
            total += self.dead_code.total_issues
        if self.duplicates:
            total += self.duplicates.total_issues
        if self.storage:
            total += self.storage.total_issues
        return total

    def as_dict(self) -> Dict:
        d = {"directory": self.directory, "total_issues": self.total_issues}
        if self.stats:
            d["stats"] = self.stats.as_dict()
        if self.dead_code:
            d["dead_code"] = self.dead_code.as_dict()
        if self.duplicates:
            d["duplicates"] = self.duplicates.as_dict()
        if self.storage:
            d["storage"] = self.storage.as_dict()
        if self.item_usage:
            d["item_usage"] = self.item_usage.as_dict()
        if self.complexity:
            d["complexity"] = self.complexity.as_dict()
        return d


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class AnalyzeEngine:
    """Runs all (or selected) analysis modules on a server directory."""

    def __init__(self, enabled_modules: Optional[List[str]] = None):
        if enabled_modules is None:
            self.enabled = set(ANALYZER_MODULES)
        else:
            self.enabled = set(enabled_modules) & set(ANALYZER_MODULES)

    def analyze(self, directory: str) -> AnalysisReport:
        """Run the full analysis."""
        report = AnalysisReport(directory=directory)

        if "stats" in self.enabled:
            logger.info("Running stats collector...")
            report.stats = collect_stats(directory)

        if "dead_code" in self.enabled:
            logger.info("Running dead code detector...")
            report.dead_code = detect_dead_code(directory)

        if "duplicates" in self.enabled:
            logger.info("Running duplicate detector...")
            report.duplicates = detect_duplicates(directory)

        if "storage" in self.enabled:
            logger.info("Running storage scanner...")
            report.storage = scan_storage(directory)

        if "item_usage" in self.enabled:
            logger.info("Running item usage scanner...")
            report.item_usage = scan_item_usage(directory)

        if "complexity" in self.enabled:
            logger.info("Running complexity analyzer...")
            report.complexity = analyze_complexity(directory)

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


def format_analysis_text(report: AnalysisReport, no_color: bool = False,
                          verbose: bool = False) -> str:
    """Format analysis report as colored text for terminal."""
    C = _Colors
    if no_color:
        # Disable all colors
        for attr in dir(C):
            if not attr.startswith("_"):
                setattr(C, attr, "")

    lines = []
    _sep = "=" * 60

    lines.append("")
    lines.append(f"  {C.BOLD}TTT Server Analysis Report{C.RESET}")
    lines.append(f"  {_sep}")
    lines.append(f"  Directory: {C.CYAN}{report.directory}{C.RESET}")
    lines.append("")

    # --- Stats ---
    if report.stats:
        s = report.stats
        sc = s.script_counts
        lines.append(f"  {C.BOLD}STATISTICS{C.RESET}")
        lines.append(f"  {'-' * 40}")
        lines.append(f"    Total Lua files:       {C.WHITE}{s.total_lua_files}{C.RESET}")
        lines.append(f"    Total XML files:       {C.WHITE}{s.total_xml_files}{C.RESET}")
        lines.append(f"    Total lines:           {C.WHITE}{s.total_lines}{C.RESET}")
        lines.append(f"    Code lines:            {C.WHITE}{s.total_code_lines}{C.RESET}")
        lines.append(f"    Functions defined:      {C.WHITE}{s.total_functions_defined}{C.RESET}")
        lines.append("")
        lines.append(f"    {C.BOLD}Scripts by type:{C.RESET}")
        for label, val in [
            ("Actions", sc.actions), ("Movements", sc.movements),
            ("TalkActions", sc.talkactions), ("CreatureScripts", sc.creaturescripts),
            ("GlobalEvents", sc.globalevents), ("Spells", sc.spells),
            ("NPCs", sc.npcs), ("Other", sc.other),
        ]:
            if val > 0 or verbose:
                lines.append(f"      {label + ':':<22} {val}")
        lines.append(f"      {'Total:':<22} {C.BOLD}{sc.total}{C.RESET}")
        lines.append("")

        lines.append(f"    {C.BOLD}API style distribution:{C.RESET}")
        for style, count in s.api_style.items():
            if count > 0 or verbose:
                color = C.RED if style == "procedural" else C.GREEN if style == "oop" else C.YELLOW
                lines.append(f"      {style + ':':<22} {color}{count}{C.RESET}")
        lines.append("")

        # Top functions
        top = s.top_functions(15)
        if top:
            lines.append(f"    {C.BOLD}Top functions:{C.RESET}")
            for name, count in top:
                lines.append(f"      {name:<40} {C.CYAN}{count} uses{C.RESET}")
            lines.append("")

        if s.version_hints:
            lines.append(f"    {C.BOLD}Version hints:{C.RESET} {', '.join(s.version_hints)}")
            lines.append("")

    # --- Dead Code ---
    if report.dead_code:
        dc = report.dead_code
        lines.append(f"  {C.BOLD}DEAD CODE{C.RESET}")
        lines.append(f"  {'-' * 40}")

        if dc.broken_xml_refs:
            lines.append(f"    {C.RED}Broken XML references ({len(dc.broken_xml_refs)}):{C.RESET}")
            for b in dc.broken_xml_refs:
                rel_xml = os.path.basename(b.xml_file)
                lines.append(f"      {rel_xml}:{b.line}  script='{b.script_ref}' -> NOT FOUND")
            lines.append("")

        if dc.orphan_scripts:
            lines.append(f"    {C.YELLOW}Orphan scripts ({len(dc.orphan_scripts)}):{C.RESET}")
            for o in dc.orphan_scripts:
                rel = os.path.relpath(o.filepath, report.directory)
                lines.append(f"      {rel}  ({o.category})")
            lines.append("")

        if dc.unused_functions:
            shown = dc.unused_functions[:20] if not verbose else dc.unused_functions
            lines.append(f"    {C.DIM}Unused functions ({len(dc.unused_functions)}):{C.RESET}")
            for u in shown:
                rel = os.path.relpath(u.filepath, report.directory)
                lines.append(f"      {rel}:{u.line}  {u.function_name}()")
            if len(dc.unused_functions) > 20 and not verbose:
                lines.append(f"      ... and {len(dc.unused_functions) - 20} more (use --verbose)")
            lines.append("")

        if not dc.broken_xml_refs and not dc.orphan_scripts and not dc.unused_functions:
            lines.append(f"    {C.GREEN}No dead code found!{C.RESET}")
            lines.append("")

    # --- Duplicates ---
    if report.duplicates:
        dup = report.duplicates
        lines.append(f"  {C.BOLD}DUPLICATES{C.RESET}")
        lines.append(f"  {'-' * 40}")

        if dup.duplicate_scripts:
            lines.append(f"    {C.YELLOW}Identical scripts ({len(dup.duplicate_scripts)} groups, "
                          f"{dup.total_duplicate_files} extra files):{C.RESET}")
            for d in dup.duplicate_scripts:
                names = [os.path.relpath(f, report.directory) for f in d.filepaths]
                lines.append(f"      Group ({d.count} files):")
                for n in names:
                    lines.append(f"        - {n}")
            lines.append("")

        if dup.duplicate_registrations:
            lines.append(f"    {C.RED}Duplicate registrations ({len(dup.duplicate_registrations)}):{C.RESET}")
            for dr in dup.duplicate_registrations:
                lines.append(f"      [{dr.reg_type}] key={dr.key}")
                for entry in dr.entries:
                    xml_name = os.path.basename(entry.get("xml_file", ""))
                    lines.append(f"        {xml_name}:{entry.get('line', '?')} -> {entry.get('script', '?')}")
            lines.append("")

        if not dup.duplicate_scripts and not dup.duplicate_registrations:
            lines.append(f"    {C.GREEN}No duplicates found!{C.RESET}")
            lines.append("")

    # --- Storage ---
    if report.storage:
        st = report.storage
        lines.append(f"  {C.BOLD}STORAGE IDS{C.RESET}")
        lines.append(f"  {'-' * 40}")
        lines.append(f"    Unique storage IDs:    {st.total_unique_ids}")
        if st.total_unique_ids > 0:
            lines.append(f"    Range:                 {st.min_id} - {st.max_id}")

        if st.conflicts:
            lines.append(f"    {C.RED}Conflicts ({len(st.conflicts)}):{C.RESET}")
            shown = st.conflicts[:10] if not verbose else st.conflicts
            for c in shown:
                files = sorted(set(os.path.relpath(u.filepath, report.directory)
                                    for u in c.usages))
                lines.append(f"      ID {c.storage_id} -> used in {c.file_count} files: "
                              f"{', '.join(files[:3])}")
            if len(st.conflicts) > 10 and not verbose:
                lines.append(f"      ... and {len(st.conflicts) - 10} more")

        if st.free_ranges:
            lines.append(f"    {C.GREEN}Available ranges (top {len(st.free_ranges)}):{C.RESET}")
            for r in st.free_ranges[:5]:
                lines.append(f"      {r.start} - {r.end}  ({r.size} IDs)")

        lines.append("")

    # --- Item Usage ---
    if report.item_usage:
        iu = report.item_usage
        lines.append(f"  {C.BOLD}ITEM USAGE{C.RESET}")
        lines.append(f"  {'-' * 40}")
        lines.append(f"    Unique item IDs:       {iu.total_unique_ids}")
        lines.append(f"    In both Lua & XML:     {C.GREEN}{len(iu.both_ids)}{C.RESET}")
        lines.append(f"    Lua only (no XML):     {C.YELLOW}{len(iu.lua_only_ids)}{C.RESET}")
        lines.append(f"    XML only (no Lua):     {C.YELLOW}{len(iu.xml_only_ids)}{C.RESET}")

        if iu.xml_only_ids and verbose:
            lines.append(f"    XML-only IDs: {sorted(iu.xml_only_ids)}")
        lines.append("")

    # --- Complexity ---
    if report.complexity:
        cx = report.complexity
        lines.append(f"  {C.BOLD}COMPLEXITY{C.RESET}")
        lines.append(f"  {'-' * 40}")
        lines.append(f"    Functions analyzed:     {cx.total_functions}")
        avg = cx.avg_complexity
        rating = cx.overall_rating
        rating_color = (C.GREEN if rating == "LOW" else
                        C.YELLOW if rating == "MEDIUM" else C.RED)
        lines.append(f"    Average complexity:     {avg:.1f} ({rating_color}{rating}{C.RESET})")

        dist = cx.distribution
        lines.append(f"    Distribution:")
        lines.append(f"      {C.GREEN}LOW (1-5):{C.RESET}         {dist['LOW']}")
        lines.append(f"      {C.YELLOW}MEDIUM (6-10):{C.RESET}     {dist['MEDIUM']}")
        lines.append(f"      {C.RED}HIGH (11-20):{C.RESET}      {dist['HIGH']}")
        lines.append(f"      {C.RED}VERY HIGH (>20):{C.RESET}   {dist['VERY HIGH']}")

        complex_funcs = cx.complex_functions(10)
        if complex_funcs:
            lines.append(f"    {C.RED}Complex functions (>= 10):{C.RESET}")
            for f in complex_funcs[:10]:
                rel = os.path.relpath(f.filepath, report.directory)
                lines.append(f"      {rel}:{f.start_line} {f.name}() "
                              f"CC={f.cyclomatic} nesting={f.max_nesting} "
                              f"lines={f.lines_of_code}")
                if f.suggestion:
                    lines.append(f"        -> {f.suggestion}")
            if len(complex_funcs) > 10 and not verbose:
                lines.append(f"      ... and {len(complex_funcs) - 10} more")

        lines.append("")

    # --- Summary ---
    lines.append(f"  {_sep}")
    total = report.total_issues
    if total == 0:
        lines.append(f"  {C.GREEN}{C.BOLD}No issues found!{C.RESET}")
    else:
        lines.append(f"  {C.YELLOW}{C.BOLD}Total issues: {total}{C.RESET}")
    lines.append("")

    return "\n".join(lines)


def format_analysis_json(report: AnalysisReport) -> str:
    """Format analysis report as JSON."""
    return json.dumps(report.as_dict(), indent=2, default=str)


def format_analysis_html(report: AnalysisReport) -> str:
    """Format analysis report as a standalone HTML page."""
    data = report.as_dict()

    stats_html = ""
    if report.stats:
        s = report.stats
        sc = s.script_counts
        top_funcs = "".join(
            f"<tr><td>{name}</td><td>{count}</td></tr>"
            for name, count in s.top_functions(20)
        )
        stats_html = f"""
        <div class="section">
            <h2>Statistics</h2>
            <div class="grid">
                <div class="card">
                    <h3>Overview</h3>
                    <table>
                        <tr><td>Lua files</td><td>{s.total_lua_files}</td></tr>
                        <tr><td>XML files</td><td>{s.total_xml_files}</td></tr>
                        <tr><td>Total lines</td><td>{s.total_lines}</td></tr>
                        <tr><td>Code lines</td><td>{s.total_code_lines}</td></tr>
                        <tr><td>Functions</td><td>{s.total_functions_defined}</td></tr>
                    </table>
                </div>
                <div class="card">
                    <h3>Script Types</h3>
                    <table>
                        <tr><td>Actions</td><td>{sc.actions}</td></tr>
                        <tr><td>Movements</td><td>{sc.movements}</td></tr>
                        <tr><td>TalkActions</td><td>{sc.talkactions}</td></tr>
                        <tr><td>CreatureScripts</td><td>{sc.creaturescripts}</td></tr>
                        <tr><td>GlobalEvents</td><td>{sc.globalevents}</td></tr>
                        <tr><td>Spells</td><td>{sc.spells}</td></tr>
                        <tr><td>NPCs</td><td>{sc.npcs}</td></tr>
                        <tr><td>Other</td><td>{sc.other}</td></tr>
                        <tr class="total"><td>Total</td><td>{sc.total}</td></tr>
                    </table>
                </div>
                <div class="card">
                    <h3>Top Functions</h3>
                    <table>
                        <tr><th>Function</th><th>Uses</th></tr>
                        {top_funcs}
                    </table>
                </div>
            </div>
        </div>
        """

    dead_code_html = ""
    if report.dead_code:
        dc = report.dead_code
        broken_rows = "".join(
            f"<tr class='error'><td>{os.path.basename(b.xml_file)}:{b.line}</td>"
            f"<td>{b.script_ref}</td><td>File not found</td></tr>"
            for b in dc.broken_xml_refs
        )
        orphan_rows = "".join(
            f"<tr class='warning'><td>{os.path.relpath(o.filepath, report.directory)}</td>"
            f"<td>{o.category}</td><td>{o.reason}</td></tr>"
            for o in dc.orphan_scripts
        )
        unused_rows = "".join(
            f"<tr><td>{os.path.relpath(u.filepath, report.directory)}:{u.line}</td>"
            f"<td colspan='2'>{u.function_name}()</td></tr>"
            for u in dc.unused_functions[:50]
        )
        dead_code_html = f"""
        <div class="section">
            <h2>Dead Code</h2>
            {"<h3>Broken XML References</h3><table><tr><th>XML</th><th>Script</th><th>Issue</th></tr>" + broken_rows + "</table>" if broken_rows else ""}
            {"<h3>Orphan Scripts</h3><table><tr><th>File</th><th>Category</th><th>Reason</th></tr>" + orphan_rows + "</table>" if orphan_rows else ""}
            {"<h3>Unused Functions</h3><table><tr><th>Location</th><th>Function</th></tr>" + unused_rows + "</table>" if unused_rows else ""}
            {"<p class='ok'>No dead code found!</p>" if dc.total_issues == 0 else ""}
        </div>
        """

    complexity_html = ""
    if report.complexity:
        cx = report.complexity
        dist = cx.distribution
        complex_rows = "".join(
            f"<tr class='{'error' if f.cyclomatic > 20 else 'warning'}'>"
            f"<td>{os.path.relpath(f.filepath, report.directory)}:{f.start_line}</td>"
            f"<td>{f.name}()</td><td>{f.cyclomatic}</td><td>{f.max_nesting}</td>"
            f"<td>{f.lines_of_code}</td><td>{f.suggestion}</td></tr>"
            for f in cx.complex_functions(10)
        )
        complexity_html = f"""
        <div class="section">
            <h2>Complexity</h2>
            <div class="grid">
                <div class="card">
                    <h3>Overview</h3>
                    <table>
                        <tr><td>Functions</td><td>{cx.total_functions}</td></tr>
                        <tr><td>Avg Complexity</td><td>{cx.avg_complexity:.1f}</td></tr>
                        <tr><td>Rating</td><td class="{cx.overall_rating.lower().replace(' ', '-')}">{cx.overall_rating}</td></tr>
                    </table>
                </div>
                <div class="card">
                    <h3>Distribution</h3>
                    <table>
                        <tr><td class="ok">LOW (1-5)</td><td>{dist['LOW']}</td></tr>
                        <tr><td class="warning">MEDIUM (6-10)</td><td>{dist['MEDIUM']}</td></tr>
                        <tr><td class="error">HIGH (11-20)</td><td>{dist['HIGH']}</td></tr>
                        <tr><td class="error">VERY HIGH (>20)</td><td>{dist['VERY HIGH']}</td></tr>
                    </table>
                </div>
            </div>
            {"<h3>Complex Functions</h3><table><tr><th>Location</th><th>Function</th><th>CC</th><th>Nesting</th><th>Lines</th><th>Suggestion</th></tr>" + complex_rows + "</table>" if complex_rows else ""}
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>TTT Server Analysis - {os.path.basename(report.directory)}</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #c9d1d9; padding: 20px; }}
  h1 {{ color: #58a6ff; margin-bottom: 5px; }}
  h2 {{ color: #58a6ff; margin: 20px 0 10px; border-bottom: 1px solid #30363d; padding-bottom: 5px; }}
  h3 {{ color: #8b949e; margin: 10px 0 5px; }}
  .section {{ margin-bottom: 30px; }}
  .grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 15px; }}
  .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px; padding: 15px; }}
  table {{ width: 100%; border-collapse: collapse; margin: 5px 0; font-size: 14px; }}
  th, td {{ padding: 6px 10px; text-align: left; border-bottom: 1px solid #21262d; }}
  th {{ color: #8b949e; font-weight: 600; }}
  tr.total td {{ font-weight: bold; border-top: 2px solid #30363d; }}
  .ok, .low {{ color: #3fb950; }}
  .warning, .medium {{ color: #d29922; }}
  .error, .high, .very-high {{ color: #f85149; }}
  .summary {{ background: #161b22; border: 1px solid #30363d; border-radius: 6px;
              padding: 15px; margin-top: 20px; text-align: center; }}
  p.ok {{ color: #3fb950; font-weight: bold; padding: 10px; }}
  .subtitle {{ color: #8b949e; }}
</style>
</head>
<body>
<h1>TTT Server Analysis Report</h1>
<p class="subtitle">{report.directory}</p>

{stats_html}
{dead_code_html}
{complexity_html}

<div class="summary">
  <p>Total issues found: <strong>{report.total_issues}</strong></p>
</div>

<p style="text-align:center; color:#484f58; margin-top:20px; font-size:12px;">
  Generated by TTT - OTServer Developer Toolkit
</p>
</body>
</html>"""
    return html
