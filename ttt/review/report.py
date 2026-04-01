"""
Review report formatters — terminal text, HTML, and JSON output.
"""

import html as html_mod
import json
from typing import List

from .models import (
    CATEGORY_LABELS,
    ReviewCategory,
    ReviewReport,
)

_SEP = "=" * 64
_THIN = "-" * 64


# ---------------------------------------------------------------------------
# Terminal text
# ---------------------------------------------------------------------------

def format_review_text(report: ReviewReport) -> str:
    """Format a ReviewReport as readable terminal text."""
    lines: List[str] = []
    lines.append("")
    lines.append(_SEP)
    lines.append("  TTT — Review Report")
    lines.append(_SEP)
    lines.append(f"  Scanned:          {report.scanned_dir}")
    lines.append(f"  Files scanned:    {report.total_files_scanned}")
    lines.append(f"  Total markers:    {report.total_markers}")
    lines.append(_SEP)

    if not report.findings:
        lines.append("")
        lines.append("  No review markers found. All clear!")
        lines.append("")
        return "\n".join(lines)

    # By category
    lines.append("")
    lines.append("  FINDINGS BY CATEGORY")
    lines.append(_THIN)
    for cat in ReviewCategory:
        items = [f for f in report.findings if f.category == cat]
        if not items:
            continue
        label = CATEGORY_LABELS.get(cat, cat.value)
        lines.append(f"  [{label}] ({len(items)})")
        for item in items:
            lines.append(f"    {item.file}:{item.line_number}")
            lines.append(f"      {item.short_text}")
        lines.append("")

    # Top blockers
    blockers = report.top_blockers()
    if blockers:
        lines.append("  TOP BLOCKERS (files with most markers)")
        lines.append(_THIN)
        for b in blockers:
            lines.append(f"    {b['file']}  ({b['count']} markers)")
        lines.append("")

    lines.append(_SEP)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------

def format_review_json(report: ReviewReport) -> str:
    """Serialize a ReviewReport to a JSON string."""
    return json.dumps(report.to_dict(), indent=2)


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def format_review_html(report: ReviewReport) -> str:
    """Generate a standalone HTML review report."""
    esc = html_mod.escape

    cat_groups = report.by_category()
    report.by_file()
    blockers = report.top_blockers()

    # Build category summary rows
    cat_rows = ""
    for cat in ReviewCategory:
        items = cat_groups.get(cat, [])
        if not items:
            continue
        label = CATEGORY_LABELS.get(cat, cat.value)
        cat_rows += f'<tr><td class="cat-{cat.value}">{esc(label)}</td><td>{len(items)}</td></tr>\n'

    # Build findings table
    finding_rows = ""
    for f in report.findings:
        label = CATEGORY_LABELS.get(f.category, f.category.value)
        snippet_html = esc(f.snippet).replace("\n", "<br>")
        finding_rows += (
            f'<tr class="cat-row cat-{f.category.value}">'
            f'<td>{esc(f.file)}:{f.line_number}</td>'
            f'<td class="cat-{f.category.value}">{esc(label)}</td>'
            f'<td>{esc(f.short_text)}</td>'
            f'<td><pre>{snippet_html}</pre></td>'
            f'</tr>\n'
        )

    # Build top blockers
    blocker_rows = ""
    for b in blockers:
        blocker_rows += f'<tr><td>{esc(b["file"])}</td><td>{b["count"]}</td></tr>\n'

    return _HTML_TEMPLATE.format(
        scanned_dir=esc(report.scanned_dir),
        total_files=report.total_files_scanned,
        total_markers=report.total_markers,
        cat_rows=cat_rows,
        finding_rows=finding_rows,
        blocker_rows=blocker_rows,
    )


_HTML_TEMPLATE = """\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>TTT Review Report</title>
<style>
:root {{
  --bg: #1e1e2e; --fg: #cdd6f4; --accent: #89b4fa;
  --card-bg: #313244; --border: #45475a;
  --red: #f38ba8; --yellow: #f9e2af; --green: #a6e3a1;
  --peach: #fab387; --mauve: #cba6f7; --teal: #94e2d5;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--fg); padding: 2rem; }}
h1 {{ color: var(--accent); margin-bottom: .5rem; }}
h2 {{ color: var(--accent); margin: 1.5rem 0 .75rem; }}
.summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 1rem; margin: 1rem 0; }}
.card {{ background: var(--card-bg); padding: 1rem; border-radius: 8px; border: 1px solid var(--border); }}
.card .label {{ font-size: .85rem; color: var(--fg); opacity: .7; }}
.card .value {{ font-size: 1.5rem; font-weight: bold; color: var(--accent); }}
table {{ width: 100%; border-collapse: collapse; margin-top: .5rem; }}
th, td {{ text-align: left; padding: .5rem .75rem; border-bottom: 1px solid var(--border); }}
th {{ background: var(--card-bg); color: var(--accent); position: sticky; top: 0; }}
tr:hover {{ background: rgba(137,180,250,0.05); }}
pre {{ font-size: .8rem; white-space: pre-wrap; word-break: break-word; max-width: 600px; }}
.cat-api-replacement {{ color: var(--peach); }}
.cat-object-unwrapping {{ color: var(--mauve); }}
.cat-unsupported-legacy {{ color: var(--red); }}
.cat-custom-function {{ color: var(--yellow); }}
.cat-confidence-risk {{ color: var(--teal); }}
.cat-general {{ color: var(--fg); }}
.filter-bar {{ margin: 1rem 0; }}
.filter-bar button {{ background: var(--card-bg); color: var(--fg); border: 1px solid var(--border);
  padding: .4rem .8rem; border-radius: 4px; cursor: pointer; margin-right: .5rem; }}
.filter-bar button:hover, .filter-bar button.active {{ background: var(--accent); color: var(--bg); }}
</style>
</head>
<body>
<h1>TTT — Review Report</h1>

<div class="summary">
  <div class="card"><div class="label">Scanned directory</div><div class="value" style="font-size:1rem">{scanned_dir}</div></div>
  <div class="card"><div class="label">Files scanned</div><div class="value">{total_files}</div></div>
  <div class="card"><div class="label">Total markers</div><div class="value">{total_markers}</div></div>
</div>

<h2>Findings by Category</h2>
<table>
<tr><th>Category</th><th>Count</th></tr>
{cat_rows}
</table>

<h2>Top Blockers</h2>
<table>
<tr><th>File</th><th>Markers</th></tr>
{blocker_rows}
</table>

<h2>All Findings</h2>
<div class="filter-bar">
  <button class="active" onclick="filterCat('all')">All</button>
  <button onclick="filterCat('api-replacement')">API Replacement</button>
  <button onclick="filterCat('object-unwrapping')">Object Unwrapping</button>
  <button onclick="filterCat('unsupported-legacy')">Unsupported Legacy</button>
  <button onclick="filterCat('custom-function')">Custom Function</button>
  <button onclick="filterCat('confidence-risk')">Confidence/Risk</button>
  <button onclick="filterCat('general')">General</button>
</div>
<table id="findings">
<tr><th>Location</th><th>Category</th><th>Marker</th><th>Context</th></tr>
{finding_rows}
</table>

<script>
function filterCat(cat) {{
  document.querySelectorAll('.filter-bar button').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  document.querySelectorAll('#findings .cat-row').forEach(row => {{
    row.style.display = (cat === 'all' || row.classList.contains('cat-' + cat)) ? '' : 'none';
  }});
}}
</script>
</body>
</html>
"""
