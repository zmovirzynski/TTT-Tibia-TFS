"""Benchmark trend tracking — Stores history and generates trend reports.

Persists benchmark results to a history JSON file and produces
release-over-release trend reports (text + HTML).
"""

import json
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from .models import BenchmarkResult

_HISTORY_FILENAME = "benchmark_history.json"


def _default_history_path() -> str:
    """Return the default benchmark history file path."""
    return os.path.join(os.getcwd(), _HISTORY_FILENAME)


def load_history(path: Optional[str] = None) -> List[Dict[str, Any]]:
    """Load benchmark history from a JSON file."""
    path = path or _default_history_path()
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []


def append_result(
    result: BenchmarkResult, path: Optional[str] = None, label: str = ""
) -> str:
    """Append a benchmark result to the history file. Returns the history path."""
    path = path or _default_history_path()
    history = load_history(path)

    entry = result.to_dict()
    entry["timestamp"] = datetime.now().isoformat()
    entry["label"] = label or result.corpus_name

    history.append(entry)

    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2)
    return path


def format_trend_text(history: List[Dict[str, Any]]) -> str:
    """Format trend data as readable terminal text."""
    if not history:
        return "No benchmark history available."

    lines = []
    sep = "=" * 70
    thin = "-" * 70

    lines.append(sep)
    lines.append("  TTT — Benchmark Trend Report")
    lines.append(sep)
    lines.append(f"  Total runs: {len(history)}")
    lines.append("")

    # Header
    lines.append(
        f"  {'Run':<5} {'Date':<20} {'Files':<7} {'Markers':<9} "
        f"{'Errors':<8} {'Duration':<10} {'Golden':<8} {'Status':<6}"
    )
    lines.append(f"  {thin}")

    for i, entry in enumerate(history):
        ts = entry.get("timestamp", "")[:19]
        files = entry.get("files_converted", 0)
        markers = entry.get("review_markers", 0)
        errors = entry.get("conversion_errors", 0)
        duration = f"{entry.get('duration_seconds', 0):.3f}s"
        golden = f"{entry.get('golden_match_rate', 1.0) * 100:.0f}%"
        status = "PASS" if entry.get("success", False) else "FAIL"
        lines.append(
            f"  {i + 1:<5} {ts:<20} {files:<7} {markers:<9} "
            f"{errors:<8} {duration:<10} {golden:<8} {status:<6}"
        )

    # Deltas (latest vs previous)
    if len(history) >= 2:
        prev = history[-2]
        curr = history[-1]
        lines.append("")
        lines.append("  Deltas (latest vs previous):")
        lines.append(f"  {thin}")

        deltas = [
            ("files_converted", "Files"),
            ("review_markers", "Markers"),
            ("conversion_errors", "Errors"),
            ("duration_seconds", "Duration"),
            ("golden_match_rate", "Golden rate"),
        ]
        for key, label in deltas:
            old_val = prev.get(key, 0)
            new_val = curr.get(key, 0)
            diff = new_val - old_val
            if key == "duration_seconds":
                sign = "+" if diff >= 0 else ""
                lines.append(
                    f"    {label:<15} {old_val:.3f}s → {new_val:.3f}s ({sign}{diff:.3f}s)"
                )
            elif key == "golden_match_rate":
                sign = "+" if diff >= 0 else ""
                lines.append(
                    f"    {label:<15} {old_val * 100:.1f}% → {new_val * 100:.1f}% ({sign}{diff * 100:.1f}%)"
                )
            else:
                sign = "+" if diff >= 0 else ""
                lines.append(f"    {label:<15} {old_val} → {new_val} ({sign}{diff})")

    lines.append("")
    lines.append(sep)
    return "\n".join(lines)


def format_trend_json(history: List[Dict[str, Any]]) -> str:
    """Serialize trend data to JSON."""
    return json.dumps(
        {
            "total_runs": len(history),
            "history": history,
        },
        indent=2,
    )


def generate_trend_html(history: List[Dict[str, Any]]) -> str:
    """Generate an HTML trend report with embedded charts."""
    if not history:
        return "<html><body><p>No benchmark history.</p></body></html>"

    # Extract data series
    labels = []
    markers_data = []
    errors_data = []
    files_data = []
    golden_data = []
    duration_data = []

    for entry in history:
        ts = entry.get("timestamp", "")[:10]
        lab = entry.get("label", ts)
        labels.append(lab)
        markers_data.append(entry.get("review_markers", 0))
        errors_data.append(entry.get("conversion_errors", 0))
        files_data.append(entry.get("files_converted", 0))
        golden_data.append(round(entry.get("golden_match_rate", 1.0) * 100, 1))
        duration_data.append(round(entry.get("duration_seconds", 0), 3))

    # Build chart data as JSON
    chart_labels = json.dumps(labels)
    chart_markers = json.dumps(markers_data)
    chart_errors = json.dumps(errors_data)
    json.dumps(files_data)
    chart_golden = json.dumps(golden_data)
    chart_duration = json.dumps(duration_data)

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TTT Benchmark Trend Report</title>
<style>
:root {{
    --bg: #1e1e2e; --fg: #cdd6f4; --accent: #89b4fa;
    --card-bg: #313244; --border: #45475a;
    --red: #f38ba8; --yellow: #f9e2af; --green: #a6e3a1;
    --peach: #fab387; --teal: #94e2d5;
}}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: 'Segoe UI', system-ui, sans-serif; background: var(--bg); color: var(--fg); padding: 2rem; }}
h1 {{ color: var(--accent); margin-bottom: .5rem; }}
h2 {{ color: var(--accent); margin: 1.5rem 0 .5rem; font-size: 1.1rem; }}
.chart-container {{ background: var(--card-bg); border-radius: 8px; padding: 1rem; margin: 1rem 0; border: 1px solid var(--border); }}
canvas {{ max-width: 100%; }}
table {{ width: 100%; border-collapse: collapse; margin-top: .5rem; }}
th, td {{ text-align: left; padding: .5rem .75rem; border-bottom: 1px solid var(--border); font-size: .85rem; }}
th {{ background: var(--card-bg); color: var(--accent); }}
.pass {{ color: var(--green); font-weight: bold; }}
.fail {{ color: var(--red); font-weight: bold; }}
</style>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
</head>
<body>
<h1>TTT Benchmark Trend Report</h1>
<p style="opacity:.6">{len(history)} run(s)</p>

<h2>Review Markers Over Time</h2>
<div class="chart-container">
<canvas id="markersChart" height="200"></canvas>
</div>

<h2>Golden Match Rate</h2>
<div class="chart-container">
<canvas id="goldenChart" height="200"></canvas>
</div>

<h2>Duration</h2>
<div class="chart-container">
<canvas id="durationChart" height="200"></canvas>
</div>

<h2>Run History</h2>
<table>
<tr><th>#</th><th>Date</th><th>Label</th><th>Files</th><th>Markers</th><th>Errors</th><th>Duration</th><th>Golden</th><th>Status</th></tr>
{
        "".join(
            f"<tr><td>{i + 1}</td><td>{e.get('timestamp', '')[:19]}</td>"
            f"<td>{e.get('label', '')}</td>"
            f"<td>{e.get('files_converted', 0)}</td>"
            f"<td>{e.get('review_markers', 0)}</td>"
            f"<td>{e.get('conversion_errors', 0)}</td>"
            f"<td>{e.get('duration_seconds', 0):.3f}s</td>"
            f"<td>{e.get('golden_match_rate', 1.0) * 100:.0f}%</td>"
            f'<td class="{"pass" if e.get("success") else "fail"}">{"PASS" if e.get("success") else "FAIL"}</td></tr>'
            for i, e in enumerate(history)
        )
    }
</table>

<script>
var labels = {chart_labels};
var cfg = {{
  responsive: true,
  plugins: {{ legend: {{ labels: {{ color: '#cdd6f4' }} }} }},
  scales: {{
    x: {{ ticks: {{ color: '#cdd6f4' }}, grid: {{ color: '#45475a' }} }},
    y: {{ ticks: {{ color: '#cdd6f4' }}, grid: {{ color: '#45475a' }}, beginAtZero: true }}
  }}
}};

new Chart(document.getElementById('markersChart'), {{
  type: 'line',
  data: {{
    labels: labels,
    datasets: [
      {{ label: 'Review Markers', data: {
        chart_markers
    }, borderColor: '#f9e2af', tension: 0.3 }},
      {{ label: 'Errors', data: {chart_errors}, borderColor: '#f38ba8', tension: 0.3 }}
    ]
  }},
  options: cfg
}});

new Chart(document.getElementById('goldenChart'), {{
  type: 'line',
  data: {{
    labels: labels,
    datasets: [{{ label: 'Golden Match %', data: {
        chart_golden
    }, borderColor: '#a6e3a1', tension: 0.3 }}]
  }},
  options: cfg
}});

new Chart(document.getElementById('durationChart'), {{
  type: 'bar',
  data: {{
    labels: labels,
    datasets: [{{ label: 'Duration (s)', data: {
        chart_duration
    }, backgroundColor: '#89b4fa' }}]
  }},
  options: cfg
}});
</script>
</body>
</html>
"""
