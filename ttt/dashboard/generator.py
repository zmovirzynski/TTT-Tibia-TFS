"""
Dashboard generator — Builds a standalone HTML dashboard from a MigrationRunReport.
"""

import html as html_mod
import json
import os
from datetime import datetime

from ..migrator.models import MigrationRunReport, StepStatus


def generate_dashboard(report: MigrationRunReport, output_path: str) -> str:
    """Generate the dashboard HTML and write to disk. Returns the HTML content."""
    gen = DashboardGenerator(report)
    return gen.generate(output_path)


class DashboardGenerator:
    """Builds a unified migration dashboard from a MigrationRunReport."""

    def __init__(self, report: MigrationRunReport):
        self.report = report

    def generate(self, output_path: str) -> str:
        """Generate the HTML dashboard, write to output_path, and return content."""
        html = self._build_html()
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html)
        return html

    def _build_html(self) -> str:
        r = self.report
        esc = html_mod.escape

        # Summary cards data
        status_class = "success" if r.success else "failed"
        status_label = "SUCCESS" if r.success else "FAILED"
        duration = f"{r.total_duration_seconds:.1f}s"

        convert_step = r.get_step("convert")
        ttt_markers = 0
        if convert_step and convert_step.ok:
            ttt_markers = convert_step.outputs.get("ttt_markers", 0)

        fix_step = r.get_step("fix")
        fixes = 0
        if fix_step and fix_step.ok:
            fixes = fix_step.outputs.get("total_fixes", 0)

        analyze_step = r.get_step("analyze")
        analysis_issues = 0
        if analyze_step and analyze_step.ok:
            analysis_issues = analyze_step.outputs.get("total_issues", 0)

        # Step rows
        step_rows = ""
        for s in r.steps:
            badge = _status_badge(s.status)
            dur = f"{s.duration_seconds:.1f}s"
            summary = esc(s.summary or s.error or "")
            step_rows += (
                f'<tr><td>{esc(s.name)}</td><td>{badge}</td>'
                f'<td>{dur}</td><td>{summary}</td></tr>\n'
            )

        # Artifact links
        artifact_rows = ""
        for label, path in r.artifacts.items():
            display = os.path.basename(path) if os.path.sep in path or "/" in path else path
            artifact_rows += (
                f'<tr><td>{esc(label)}</td>'
                f'<td><a href="{esc(display)}" target="_blank">{esc(display)}</a></td></tr>\n'
            )

        # File-level rows
        file_rows = ""
        for fe in r.file_entries:
            conf_badge = _confidence_badge(fe.confidence)
            markers_cell = f'<span class="marker-count warn">{fe.ttt_markers}</span>' if fe.ttt_markers > 0 else '<span class="marker-count clean">0</span>'
            diff_link = ""
            if fe.has_diff:
                diff_link = '<a href="conversion_diff.html" target="_blank">diff</a>'
            file_rows += (
                f'<tr data-confidence="{esc(fe.confidence.lower())}" data-markers="{fe.ttt_markers}">'
                f'<td>{esc(fe.path)}</td>'
                f'<td>{esc(fe.file_type)}</td>'
                f'<td>{fe.changes}</td>'
                f'<td>{markers_cell}</td>'
                f'<td>{conf_badge}</td>'
                f'<td>{diff_link}</td></tr>\n'
            )
        has_file_table = len(r.file_entries) > 0

        # Conditional CSS classes for warning values
        ttt_marker_class = " warn" if ttt_markers > 0 else ""
        doctor_class = " warn" if r.doctor_issues > 0 else ""

        return _DASHBOARD_HTML.format(
            status_class=status_class,
            status_label=status_label,
            input_dir=esc(r.input_dir),
            output_dir=esc(r.output_dir or "(dry-run)"),
            source_version=esc(r.source_version),
            target_version=esc(r.target_version),
            duration=duration,
            files_converted=r.files_converted,
            ttt_markers=ttt_markers,
            ttt_marker_class=ttt_marker_class,
            health_score=r.health_score if r.health_score is not None else "N/A",
            health_rating=esc(r.health_rating),
            doctor_issues=r.doctor_issues,
            doctor_class=doctor_class,
            analysis_issues=analysis_issues,
            fixes_applied=fixes,
            step_rows=step_rows,
            artifact_rows=artifact_rows,
            file_rows=file_rows,
            file_section_display="block" if has_file_table else "none",
            generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            report_json=html_mod.escape(json.dumps(r.to_dict(), indent=2)),
        )


def _status_badge(status: StepStatus) -> str:
    """Return an HTML badge for a step status."""
    colors = {
        StepStatus.SUCCESS: "#a6e3a1",
        StepStatus.FAILED: "#f38ba8",
        StepStatus.SKIPPED: "#6c7086",
        StepStatus.RUNNING: "#89b4fa",
        StepStatus.PENDING: "#9399b2",
    }
    color = colors.get(status, "#9399b2")
    label = status.value.upper()
    return f'<span class="badge" style="background:{color}">{label}</span>'


def _confidence_badge(confidence: str) -> str:
    """Return an HTML badge for a file confidence level."""
    colors = {
        "HIGH": "#a6e3a1",
        "MEDIUM": "#f9e2af",
        "LOW": "#fab387",
        "REVIEW": "#f38ba8",
    }
    color = colors.get(confidence.upper(), "#9399b2")
    return f'<span class="badge" style="background:{color}">{confidence.upper()}</span>'


_DASHBOARD_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TTT Migration Dashboard</title>
<style>
:root {{
  --bg: #1e1e2e; --fg: #cdd6f4; --accent: #89b4fa;
  --card-bg: #313244; --border: #45475a;
  --red: #f38ba8; --yellow: #f9e2af; --green: #a6e3a1;
  --peach: #fab387; --mauve: #cba6f7; --teal: #94e2d5;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--fg); padding: 2rem; }}
h1 {{ color: var(--accent); margin-bottom: .25rem; }}
.subtitle {{ color: var(--fg); opacity: .6; margin-bottom: 1.5rem; }}
h2 {{ color: var(--accent); margin: 2rem 0 .75rem; font-size: 1.2rem; }}

/* Cards grid */
.cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 1rem; margin: 1.5rem 0; }}
.card {{ background: var(--card-bg); padding: 1rem; border-radius: 8px; border: 1px solid var(--border); }}
.card .label {{ font-size: .8rem; color: var(--fg); opacity: .6; text-transform: uppercase; letter-spacing: .5px; }}
.card .value {{ font-size: 1.8rem; font-weight: bold; color: var(--accent); margin-top: .25rem; }}
.card .value.success {{ color: var(--green); }}
.card .value.failed {{ color: var(--red); }}
.card .value.warn {{ color: var(--yellow); }}

/* Tables */
table {{ width: 100%; border-collapse: collapse; margin-top: .5rem; }}
th, td {{ text-align: left; padding: .6rem .75rem; border-bottom: 1px solid var(--border); }}
th {{ background: var(--card-bg); color: var(--accent); position: sticky; top: 0; font-size: .85rem; text-transform: uppercase; letter-spacing: .5px; }}
tr:hover {{ background: rgba(137,180,250,0.05); }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}

/* Badges */
.badge {{ display: inline-block; padding: .15rem .5rem; border-radius: 4px; font-size: .75rem; font-weight: 600; color: #1e1e2e; }}

/* Info bar */
.info-bar {{ display: flex; flex-wrap: wrap; gap: 1.5rem; background: var(--card-bg); padding: .75rem 1rem; border-radius: 6px; margin-bottom: 1.5rem; font-size: .85rem; }}
.info-bar span {{ color: var(--fg); opacity: .8; }}
.info-bar strong {{ color: var(--accent); }}

/* Trend placeholder */
.trend-placeholder {{ background: var(--card-bg); border: 2px dashed var(--border); border-radius: 8px; padding: 2rem; text-align: center; color: var(--fg); opacity: .4; margin: 1rem 0; }}

/* Filter bar */
.filter-bar {{ display: flex; flex-wrap: wrap; gap: .5rem; margin: .75rem 0; align-items: center; }}
.filter-bar label {{ font-size: .8rem; color: var(--fg); opacity: .6; margin-right: .25rem; }}
.filter-btn {{ background: var(--card-bg); color: var(--fg); border: 1px solid var(--border); border-radius: 4px; padding: .3rem .7rem; cursor: pointer; font-size: .8rem; }}
.filter-btn:hover {{ border-color: var(--accent); }}
.filter-btn.active {{ background: var(--accent); color: var(--bg); border-color: var(--accent); }}
.filter-input {{ background: var(--card-bg); color: var(--fg); border: 1px solid var(--border); border-radius: 4px; padding: .3rem .5rem; font-size: .8rem; width: 200px; }}
.filter-input::placeholder {{ color: var(--fg); opacity: .4; }}

/* Marker counts */
.marker-count {{ font-weight: 600; }}
.marker-count.warn {{ color: var(--yellow); }}
.marker-count.clean {{ color: var(--green); opacity: .6; }}

/* Responsive */
@media (max-width: 768px) {{
  body {{ padding: 1rem; }}
  .cards {{ grid-template-columns: repeat(2, 1fr); }}
}}
</style>
</head>
<body>

<h1>TTT Migration Dashboard</h1>
<p class="subtitle">Generated {generated_at}</p>

<div class="info-bar">
  <span>Input: <strong>{input_dir}</strong></span>
  <span>Output: <strong>{output_dir}</strong></span>
  <span>Conversion: <strong>{source_version} → {target_version}</strong></span>
  <span>Duration: <strong>{duration}</strong></span>
</div>

<div class="cards">
  <div class="card">
    <div class="label">Status</div>
    <div class="value {status_class}">{status_label}</div>
  </div>
  <div class="card">
    <div class="label">Files Converted</div>
    <div class="value">{files_converted}</div>
  </div>
  <div class="card">
    <div class="label">Review Markers</div>
    <div class="value{ttt_marker_class}">{ttt_markers}</div>
  </div>
  <div class="card">
    <div class="label">Health Score</div>
    <div class="value">{health_score}<span style="font-size:.8rem;opacity:.6">/{health_rating}</span></div>
  </div>
  <div class="card">
    <div class="label">Doctor Issues</div>
    <div class="value{doctor_class}">{doctor_issues}</div>
  </div>
  <div class="card">
    <div class="label">Analysis Issues</div>
    <div class="value">{analysis_issues}</div>
  </div>
  <div class="card">
    <div class="label">Auto-Fixes</div>
    <div class="value">{fixes_applied}</div>
  </div>
</div>

<h2>Pipeline Steps</h2>
<table>
<tr><th>Step</th><th>Status</th><th>Duration</th><th>Summary</th></tr>
{step_rows}
</table>

<h2>Artifacts</h2>
<table>
<tr><th>Label</th><th>File</th></tr>
{artifact_rows}
</table>

<div id="file-section" style="display:{file_section_display}">
<h2>Converted Files</h2>
<div class="filter-bar">
  <label>Confidence:</label>
  <button class="filter-btn active" data-filter="all" onclick="filterFiles(this)">All</button>
  <button class="filter-btn" data-filter="review" onclick="filterFiles(this)">Review</button>
  <button class="filter-btn" data-filter="low" onclick="filterFiles(this)">Low</button>
  <button class="filter-btn" data-filter="medium" onclick="filterFiles(this)">Medium</button>
  <button class="filter-btn" data-filter="high" onclick="filterFiles(this)">High</button>
  <span style="margin-left:.5rem"></span>
  <button class="filter-btn" id="markers-btn" onclick="toggleMarkers(this)">Has Markers</button>
  <span style="margin-left:.5rem"></span>
  <input class="filter-input" id="file-search" placeholder="Search filename..." oninput="applyFilters()">
</div>
<table id="file-table">
<tr><th>File</th><th>Type</th><th>Changes</th><th>Markers</th><th>Confidence</th><th>Diff</th></tr>
{file_rows}
</table>
</div>

<h2>Regression Trend</h2>
<div class="trend-placeholder">
  Trend charts will appear here when benchmark history is available.<br>
  Run <code>ttt benchmark</code> across versions to populate.
</div>

<script>
// Embed report data for downstream tooling
window.__TTT_REPORT__ = {report_json};

// File table filtering
var activeConfidence = 'all';
var markersOnly = false;

function filterFiles(btn) {{
  activeConfidence = btn.getAttribute('data-filter');
  document.querySelectorAll('.filter-bar .filter-btn[data-filter]').forEach(function(b) {{
    b.classList.remove('active');
  }});
  btn.classList.add('active');
  applyFilters();
}}

function toggleMarkers(btn) {{
  markersOnly = !markersOnly;
  btn.classList.toggle('active', markersOnly);
  applyFilters();
}}

function applyFilters() {{
  var search = (document.getElementById('file-search').value || '').toLowerCase();
  var rows = document.querySelectorAll('#file-table tr[data-confidence]');
  rows.forEach(function(row) {{
    var conf = row.getAttribute('data-confidence');
    var markers = parseInt(row.getAttribute('data-markers') || '0', 10);
    var text = row.cells[0].textContent.toLowerCase();
    var show = true;
    if (activeConfidence !== 'all' && conf !== activeConfidence) show = false;
    if (markersOnly && markers === 0) show = false;
    if (search && text.indexOf(search) === -1) show = false;
    row.style.display = show ? '' : 'none';
  }});
}}
</script>

</body>
</html>
"""
