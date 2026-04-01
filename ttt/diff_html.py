"""
HTML Diff Generator.

Generates a standalone HTML page with side-by-side visual diffs
of original vs converted scripts. Includes:
  - Dark themed UI with Lua syntax-aware highlighting
  - File navigation sidebar with on-demand rendering
  - Line-by-line diff (additions, removals, changes)
  - Word-level highlighting for changed lines (computed in JS)
  - Conversion summary and stats
  - Zero external dependencies (self-contained HTML/CSS/JS)

File content is stored as compact JSON and rendered client-side when
a file is selected, keeping the HTML size proportional to the number
of diff lines rather than the total lines across all files.
"""

import os
import json
import difflib
import html
from datetime import datetime
from typing import Dict, List
from dataclasses import dataclass


@dataclass
class DiffEntry:
    """Entrada de diff de um arquivo."""

    filename: str
    source_path: str = ""
    original: str = ""
    converted: str = ""
    file_type: str = ""
    confidence: str = ""
    functions_converted: int = 0
    total_changes: int = 0


class HtmlDiffGenerator:
    """Monta a página HTML standalone com diff lado a lado."""

    def __init__(
        self, source_version: str, target_version: str, input_dir: str, output_dir: str
    ):
        self.source_version = source_version
        self.target_version = target_version
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.entries: List[DiffEntry] = []
        self._guidelines_md: str = ""

    def set_guidelines(self, content: str):
        self._guidelines_md = content

    def add_entry(self, entry: DiffEntry):
        if entry.original or entry.converted:
            self.entries.append(entry)

    def generate(self, output_path: str) -> str:
        """Gera o HTML e salva em disco. Retorna o conteúdo."""
        html_content = self._build_html()
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(html_content)
        return html_content

    # ── Diff computation ───────────────────────────────────────────────────

    def _compute_diff_lines(self, original: str, converted: str) -> List[dict]:
        """Calcula diff lado a lado. Retorna lista de dicts (left/right + status)."""
        orig_lines = original.splitlines()
        conv_lines = converted.splitlines()

        matcher = difflib.SequenceMatcher(None, orig_lines, conv_lines)
        result = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    result.append(
                        {
                            "status": "equal",
                            "left_num": i + 1,
                            "left_line": orig_lines[i],
                            "right_num": j + 1,
                            "right_line": conv_lines[j],
                        }
                    )
            elif tag == "replace":
                max_len = max(i2 - i1, j2 - j1)
                for k in range(max_len):
                    left_idx = i1 + k if k < (i2 - i1) else None
                    right_idx = j1 + k if k < (j2 - j1) else None
                    result.append(
                        {
                            "status": "change",
                            "left_num": (left_idx + 1)
                            if left_idx is not None
                            else None,
                            "left_line": orig_lines[left_idx]
                            if left_idx is not None
                            else None,
                            "right_num": (right_idx + 1)
                            if right_idx is not None
                            else None,
                            "right_line": conv_lines[right_idx]
                            if right_idx is not None
                            else None,
                        }
                    )
            elif tag == "delete":
                for i in range(i1, i2):
                    result.append(
                        {
                            "status": "remove",
                            "left_num": i + 1,
                            "left_line": orig_lines[i],
                            "right_num": None,
                            "right_line": None,
                        }
                    )
            elif tag == "insert":
                for j in range(j1, j2):
                    result.append(
                        {
                            "status": "add",
                            "left_num": None,
                            "left_line": None,
                            "right_num": j + 1,
                            "right_line": conv_lines[j],
                        }
                    )

        return result

    def _compact_diff(self, diff_lines: List[dict]) -> List:
        """
        Convert diff lines to a compact array format for JSON serialization.

        Format per entry (first element is status code):
          equal:  ["e", left_num, right_num, content]        (4 elements, content shared)
          change: ["c", left_num, left_line, right_num, right_line]  (5 elements)
          remove: ["r", left_num, left_line]                 (3 elements)
          add:    ["a", right_num, right_line]               (3 elements)
        """
        result = []
        for dl in diff_lines:
            s = dl["status"]
            if s == "equal":
                result.append(["e", dl["left_num"], dl["right_num"], dl["left_line"]])
            elif s == "change":
                result.append(
                    [
                        "c",
                        dl["left_num"],
                        dl["left_line"] or "",
                        dl["right_num"],
                        dl["right_line"] or "",
                    ]
                )
            elif s == "remove":
                result.append(["r", dl["left_num"], dl["left_line"] or ""])
            else:  # add
                result.append(["a", dl["right_num"], dl["right_line"] or ""])
        return result

    # ── HTML builder ───────────────────────────────────────────────────────

    def _build_html(self) -> str:
        total_files = len(self.entries)
        files_changed = sum(1 for e in self.entries if e.original != e.converted)
        total_funcs = sum(e.functions_converted for e in self.entries)
        total_changes = sum(e.total_changes for e in self.entries)

        nav_items_html = []
        file_data: Dict[str, dict] = {}
        first_changed_id = ""

        for idx, entry in enumerate(self.entries):
            file_id = f"file-{idx}"
            has_changes = entry.original != entry.converted
            badge_class = "badge-changed" if has_changes else "badge-same"
            badge_text = "CHANGED" if has_changes else "NO CHANGES"
            type_label = entry.file_type.upper() if entry.file_type else "LUA"

            if has_changes and not first_changed_id:
                first_changed_id = file_id

            nav_items_html.append(
                f'<a href="#{file_id}" class="nav-item" data-id="{file_id}"'
                f' data-changed="{str(has_changes).lower()}"'
                f" onclick=\"return selectFile('{file_id}')\">"
                f'<span class="nav-type {_esc(entry.file_type)}">{_esc(type_label)}</span>'
                f'<span class="nav-name">{_esc(entry.filename)}</span>'
                f'<span class="nav-badge {badge_class}">{badge_text}</span>'
                f"</a>"
            )

            compact_diff = (
                self._compact_diff(
                    self._compute_diff_lines(entry.original, entry.converted)
                )
                if has_changes
                else None
            )

            file_data[file_id] = {
                "fn": entry.filename,
                "ft": entry.file_type or "",
                "tl": type_label,
                "cf": entry.confidence or "",
                "fc": entry.functions_converted,
                "tc": entry.total_changes,
                "hc": has_changes,
                "dl": compact_diff,
            }

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        auto_select = first_changed_id or ("file-0" if self.entries else "")

        if self._guidelines_md:
            guidelines_nav = (
                '<div class="sidebar-nav-title" style="margin-top:12px">Analysis</div>'
                '<a href="#" class="nav-item" data-id="llm-guide" data-changed="false"'
                ' onclick="return selectGuide()">'
                '<span class="nav-type" style="background:#1a2a3a;color:#58a6ff">LLM</span>'
                '<span class="nav-name">LLM Refactoring Guide</span>'
                "</a>"
            )
            guidelines_data = json.dumps(
                _render_guidelines_html(self._guidelines_md), ensure_ascii=False
            )
        else:
            guidelines_nav = ""
            guidelines_data = "null"

        return _HTML_TEMPLATE.format(
            source_version=_esc(self.source_version),
            target_version=_esc(self.target_version),
            input_dir=_esc(self.input_dir),
            output_dir=_esc(self.output_dir),
            date=_esc(now_str),
            total_files=total_files,
            files_changed=files_changed,
            total_funcs=total_funcs,
            total_changes=total_changes,
            nav_items="\n".join(nav_items_html),
            guidelines_nav=guidelines_nav,
            file_data_json=json.dumps(file_data, ensure_ascii=False),
            guidelines_data=guidelines_data,
            auto_select=auto_select,
        )


# ── Markdown → HTML (for guidelines section) ──────────────────────────────


def _render_guidelines_html(md: str) -> str:
    """Render Markdown guidelines to an HTML string."""
    parts = [
        '<div class="guidelines-section" id="llm-refactor-guide">',
        '<div class="guidelines-header">',
        "<h2>LLM Refactoring Guide</h2>",
        "<p>Per-file analysis and prompts for AI-assisted OOP conversion</p>",
        "</div>",
        '<div class="guidelines-body">',
    ]
    in_ul = False
    for line in md.split("\n"):
        if line.startswith("# "):
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            parts.append(f"<h1>{_md_inline(line[2:])}</h1>")
        elif line.startswith("## "):
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            parts.append(f"<h2>{_md_inline(line[3:])}</h2>")
        elif line.startswith("### "):
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            parts.append(f"<h3>{_md_inline(line[4:])}</h3>")
        elif line.startswith("> "):
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            parts.append(f"<blockquote>{_md_inline(line[2:])}</blockquote>")
        elif line.startswith("- "):
            if not in_ul:
                parts.append("<ul>")
                in_ul = True
            parts.append(f"<li>{_md_inline(line[2:])}</li>")
        elif line == "---":
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            parts.append("<hr>")
        elif line == "":
            if in_ul:
                parts.append("</ul>")
                in_ul = False
        else:
            if in_ul:
                parts.append("</ul>")
                in_ul = False
            parts.append(f"<p>{_md_inline(line)}</p>")
    if in_ul:
        parts.append("</ul>")
    parts.append("</div></div>")
    return "\n".join(parts)


def _md_inline(text: str) -> str:
    import re as _re

    text = html.escape(text)
    text = _re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = _re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    return text


def _esc(text: str) -> str:
    return html.escape(str(text))


# ── HTML Template ──────────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>TTT — Visual Diff · {source_version} → {target_version}</title>
<style>
:root {{
    --bg-dark: #0d1117;
    --bg-card: #161b22;
    --bg-sidebar: #0d1117;
    --bg-header: #1c2128;
    --border: #30363d;
    --text: #e6edf3;
    --text-muted: #8b949e;
    --accent: #58a6ff;
    --accent-dim: #1f6feb33;
    --green-bg: #12261e;
    --green-line: #1a3a2a;
    --green-word: #2ea04366;
    --red-bg: #2d1214;
    --red-line: #3d1a1e;
    --red-word: #f8514966;
    --change-bg: #2a2000;
    --yellow-word: #e3b34166;
    --font-mono: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
}}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--bg-dark); color:var(--text); font-family:var(--font-sans); line-height:1.5; }}
.layout {{ display:flex; min-height:100vh; }}
.sidebar {{ width:280px; min-width:280px; background:var(--bg-sidebar); border-right:1px solid var(--border); display:flex; flex-direction:column; position:sticky; top:0; height:100vh; overflow-y:auto; }}
.main {{ flex:1; padding:24px; overflow-x:auto; min-width:0; }}
.sidebar-header {{ padding:20px 16px; border-bottom:1px solid var(--border); }}
.sidebar-header h1 {{ font-size:16px; font-weight:600; color:var(--accent); margin-bottom:4px; }}
.sidebar-header .subtitle {{ font-size:12px; color:var(--text-muted); }}
.sidebar-stats {{ padding:12px 16px; border-bottom:1px solid var(--border); display:grid; grid-template-columns:1fr 1fr; gap:8px; }}
.stat-box {{ background:var(--bg-card); border-radius:6px; padding:8px 10px; text-align:center; }}
.stat-value {{ font-size:20px; font-weight:700; color:var(--accent); display:block; }}
.stat-label {{ font-size:10px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; }}
.sidebar-filter {{ padding:8px 16px; border-bottom:1px solid var(--border); display:flex; gap:6px; flex-wrap:wrap; }}
.filter-btn {{ background:var(--bg-card); border:1px solid var(--border); color:var(--text-muted); padding:4px 10px; border-radius:5px; cursor:pointer; font-size:11px; font-family:var(--font-sans); transition:all 0.15s; }}
.filter-btn:hover {{ border-color:var(--accent); color:var(--text); }}
.filter-btn.active {{ background:var(--accent-dim); border-color:var(--accent); color:var(--accent); }}
.sidebar-nav {{ flex:1; overflow-y:auto; padding:8px 0; }}
.sidebar-nav-title {{ padding:8px 16px 4px; font-size:11px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; font-weight:600; }}
.nav-item {{ display:flex; align-items:center; gap:8px; padding:6px 16px; text-decoration:none; color:var(--text); font-size:13px; border-left:2px solid transparent; transition:all 0.15s; cursor:pointer; }}
.nav-item:hover {{ background:var(--bg-card); border-left-color:var(--accent); }}
.nav-item.active {{ background:var(--accent-dim); border-left-color:var(--accent); }}
.nav-type {{ font-size:9px; font-weight:700; text-transform:uppercase; background:#30363d; color:var(--text-muted); padding:1px 5px; border-radius:3px; min-width:40px; text-align:center; flex-shrink:0; }}
.nav-type.action {{ background:#1a3a2a; color:#3fb950; }}
.nav-type.movement {{ background:#2a2000; color:#d29922; }}
.nav-type.talkaction {{ background:#1a1a3a; color:#8b8bff; }}
.nav-type.creaturescript {{ background:#3a1a2a; color:#f85149; }}
.nav-type.globalevent {{ background:#1a2a3a; color:#58a6ff; }}
.nav-type.npc {{ background:#2a1a3a; color:#bc8cff; }}
.nav-name {{ flex:1; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
.nav-badge {{ font-size:9px; font-weight:600; padding:1px 6px; border-radius:10px; flex-shrink:0; }}
.badge-changed {{ background:#d292221a; color:#d29922; border:1px solid #d2992233; }}
.badge-same {{ background:#3fb9501a; color:#3fb950; border:1px solid #3fb95033; }}
.page-header {{ margin-bottom:24px; padding-bottom:16px; border-bottom:1px solid var(--border); }}
.page-header h2 {{ font-size:22px; font-weight:600; margin-bottom:4px; }}
.page-header p {{ color:var(--text-muted); font-size:13px; }}
.summary-row {{ display:flex; gap:12px; margin-bottom:24px; flex-wrap:wrap; }}
.summary-card {{ background:var(--bg-card); border:1px solid var(--border); border-radius:8px; padding:16px 20px; flex:1; min-width:140px; }}
.summary-card .label {{ font-size:11px; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; }}
.summary-card .value {{ font-size:28px; font-weight:700; color:var(--accent); margin-top:2px; }}
.file-card {{ background:var(--bg-card); border:1px solid var(--border); border-radius:8px; margin-bottom:20px; overflow:hidden; }}
.file-header {{ display:flex; justify-content:space-between; align-items:center; padding:12px 16px; background:var(--bg-header); border-bottom:1px solid var(--border); flex-wrap:wrap; gap:8px; }}
.file-info {{ display:flex; align-items:center; gap:8px; }}
.file-type-badge {{ font-size:10px; font-weight:700; text-transform:uppercase; background:#30363d; color:var(--text-muted); padding:2px 8px; border-radius:4px; }}
.file-type-badge.action {{ background:#1a3a2a; color:#3fb950; }}
.file-type-badge.movement {{ background:#2a2000; color:#d29922; }}
.file-type-badge.talkaction {{ background:#1a1a3a; color:#8b8bff; }}
.file-type-badge.creaturescript {{ background:#3a1a2a; color:#f85149; }}
.file-type-badge.globalevent {{ background:#1a2a3a; color:#58a6ff; }}
.file-type-badge.npc {{ background:#2a1a3a; color:#bc8cff; }}
.file-name {{ font-size:14px; font-weight:600; font-family:var(--font-mono); }}
.file-badge {{ font-size:9px; font-weight:600; padding:1px 6px; border-radius:10px; }}
.file-stats {{ font-size:12px; color:var(--text-muted); }}
.diff-labels {{ display:flex; border-bottom:1px solid var(--border); }}
.diff-label-left, .diff-label-right {{ flex:1; padding:6px 16px; font-size:11px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; }}
.diff-label-left {{ border-right:1px solid var(--border); background:#2d12140a; }}
.diff-label-right {{ background:#12261e0a; }}
.diff-container {{ overflow-x:auto; }}
.no-changes {{ padding:32px; text-align:center; color:var(--text-muted); font-style:italic; }}
.no-file-selected {{ padding:60px 32px; text-align:center; color:var(--text-muted); font-size:14px; background:var(--bg-card); border:1px solid var(--border); border-radius:8px; }}
.diff-table {{ width:100%; border-collapse:collapse; font-family:var(--font-mono); font-size:12.5px; line-height:1.5; table-layout:fixed; }}
.diff-table td {{ padding:0 8px; vertical-align:top; white-space:pre; overflow:hidden; }}
.diff-table .line-num {{ width:42px; min-width:42px; text-align:right; color:var(--text-muted); user-select:none; opacity:0.5; font-size:11px; padding-right:6px; }}
.diff-table .diff-marker {{ width:14px; min-width:14px; text-align:center; color:var(--text-muted); user-select:none; font-weight:700; }}
.diff-table .code-cell {{ width:calc(50% - 56px); }}
.diff-table .divider {{ width:1px; min-width:1px; background:var(--border); padding:0; }}
.diff-equal .code-cell {{ background:transparent; }}
.diff-change .code-cell.left {{ background:var(--red-bg); }}
.diff-change .code-cell.right {{ background:var(--green-bg); }}
.diff-change .diff-marker {{ color:#d29922; }}
.diff-remove .code-cell.left {{ background:var(--red-bg); }}
.diff-remove .diff-marker {{ color:#f85149; }}
.diff-add .code-cell.right {{ background:var(--green-bg); }}
.diff-add .diff-marker {{ color:#3fb950; }}
.word-del {{ background:var(--red-word); border-radius:2px; padding:0 1px; }}
.word-add {{ background:var(--green-word); border-radius:2px; padding:0 1px; }}
.footer {{ margin-top:32px; padding-top:16px; border-top:1px solid var(--border); text-align:center; color:var(--text-muted); font-size:12px; }}
@media (max-width:900px) {{ .sidebar {{ display:none; }} .main {{ padding:12px; }} }}
.guidelines-section {{ background:var(--bg-card); border:1px solid var(--border); border-radius:8px; margin-bottom:20px; overflow:hidden; }}
.guidelines-header {{ padding:16px 20px; background:var(--bg-header); border-bottom:1px solid var(--border); }}
.guidelines-header h2 {{ font-size:18px; font-weight:600; color:var(--accent); margin-bottom:4px; }}
.guidelines-header p {{ font-size:12px; color:var(--text-muted); }}
.guidelines-body {{ padding:20px 24px; font-size:13px; line-height:1.7; }}
.guidelines-body h1 {{ font-size:20px; font-weight:700; color:var(--text); margin:24px 0 12px; padding-bottom:8px; border-bottom:1px solid var(--border); }}
.guidelines-body h2 {{ font-size:15px; font-weight:600; color:var(--accent); margin:20px 0 8px; padding-bottom:4px; border-bottom:1px solid var(--border); }}
.guidelines-body h3 {{ font-size:13px; font-weight:600; color:var(--text-muted); text-transform:uppercase; letter-spacing:0.5px; margin:16px 0 6px; }}
.guidelines-body p {{ margin:0 0 8px; color:var(--text); }}
.guidelines-body ul {{ margin:4px 0 12px 20px; color:var(--text); }}
.guidelines-body li {{ margin-bottom:4px; }}
.guidelines-body blockquote {{ border-left:3px solid var(--accent); padding:8px 16px; margin:8px 0; color:var(--text-muted); background:var(--accent-dim); border-radius:0 4px 4px 0; font-style:italic; }}
.guidelines-body hr {{ border:none; border-top:1px solid var(--border); margin:16px 0; }}
.guidelines-body code {{ font-family:var(--font-mono); font-size:11.5px; background:#30363d; padding:1px 5px; border-radius:3px; color:#e6edf3; }}
.guidelines-body strong {{ font-weight:600; color:var(--text); }}
</style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <div class="sidebar-header">
      <h1>TTT — Visual Diff</h1>
      <div class="subtitle">{source_version} → {target_version}</div>
    </div>
    <div class="sidebar-stats">
      <div class="stat-box"><span class="stat-value">{total_files}</span><span class="stat-label">Files</span></div>
      <div class="stat-box"><span class="stat-value">{files_changed}</span><span class="stat-label">Changed</span></div>
      <div class="stat-box"><span class="stat-value">{total_funcs}</span><span class="stat-label">Functions</span></div>
      <div class="stat-box"><span class="stat-value">{total_changes}</span><span class="stat-label">Changes</span></div>
    </div>
    <div class="sidebar-filter">
      <button class="filter-btn active" onclick="filterNav('all',this)">All</button>
      <button class="filter-btn" onclick="filterNav('changed',this)">Changed</button>
      <button class="filter-btn" onclick="filterNav('same',this)">No changes</button>
    </div>
    <div class="sidebar-nav">
      <div class="sidebar-nav-title">Files</div>
      {nav_items}
      {guidelines_nav}
    </div>
  </aside>

  <main class="main">
    <div class="page-header">
      <h2>Conversion Diff Report</h2>
      <p>{source_version} → {target_version} · {date} · Input: {input_dir}</p>
    </div>
    <div class="summary-row">
      <div class="summary-card"><div class="label">Files Analyzed</div><div class="value">{total_files}</div></div>
      <div class="summary-card"><div class="label">Files Changed</div><div class="value">{files_changed}</div></div>
      <div class="summary-card"><div class="label">Functions Converted</div><div class="value">{total_funcs}</div></div>
      <div class="summary-card"><div class="label">Total Changes</div><div class="value">{total_changes}</div></div>
    </div>
    <div id="file-view">
      <div class="no-file-selected">← Select a file from the sidebar to view its diff</div>
    </div>
    <div class="footer">Generated by TTT — TFS Script Converter v2.0 · {date}</div>
  </main>
</div>

<script id="file-data" type="application/json">{file_data_json}</script>
<script>
var FILES = JSON.parse(document.getElementById('file-data').textContent);
var GUIDELINES = {guidelines_data};
var SRC = '{source_version}';
var TGT = '{target_version}';

// ── Utilities ────────────────────────────────────────────────────────────

function esc(s) {{
  return String(s == null ? '' : s)
    .replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

function tokenize(s) {{
  return s.match(/\S+|\s+/g) || [];
}}

// Simple LCS-based word diff
function wordDiff(left, right) {{
  var lt = tokenize(left), rt = tokenize(right);
  // Skip word diff for very long lines to avoid O(n²) slowdown
  if (lt.length > 120 || rt.length > 120) {{
    return ['<span class="word-del">' + esc(left) + '</span>',
            '<span class="word-add">' + esc(right) + '</span>'];
  }}
  var m = lt.length, n = rt.length;
  var dp = [];
  for (var i = 0; i <= m; i++) {{
    dp[i] = new Array(n + 1).fill(0);
  }}
  for (var i = 1; i <= m; i++) {{
    for (var j = 1; j <= n; j++) {{
      dp[i][j] = lt[i-1] === rt[j-1] ? dp[i-1][j-1] + 1 : Math.max(dp[i-1][j], dp[i][j-1]);
    }}
  }}
  var lp = [], rp = [], i = m, j = n;
  while (i > 0 || j > 0) {{
    if (i > 0 && j > 0 && lt[i-1] === rt[j-1]) {{
      lp.unshift(esc(lt[i-1])); rp.unshift(esc(rt[j-1])); i--; j--;
    }} else if (j > 0 && (i === 0 || dp[i][j-1] >= dp[i-1][j])) {{
      rp.unshift('<span class="word-add">' + esc(rt[j-1]) + '</span>'); j--;
    }} else {{
      lp.unshift('<span class="word-del">' + esc(lt[i-1]) + '</span>'); i--;
    }}
  }}
  return [lp.join(''), rp.join('')];
}}

// ── Diff table renderer ──────────────────────────────────────────────────

function renderDiffTable(diffLines) {{
  var rows = [];
  var STATUS = {{ e:'diff-equal', c:'diff-change', r:'diff-remove', a:'diff-add' }};
  var LM = {{ e:' ', c:'~', r:'-', a:' ' }};
  var RM = {{ e:' ', c:'~', r:' ', a:'+' }};

  for (var i = 0; i < diffLines.length; i++) {{
    var dl = diffLines[i], s = dl[0];
    var ln, ll, rn, rl;
    if (s === 'e') {{ ln = dl[1]; rn = dl[2]; ll = rl = dl[3]; }}
    else if (s === 'c') {{ ln = dl[1]; ll = dl[2]; rn = dl[3]; rl = dl[4]; }}
    else if (s === 'r') {{ ln = dl[1]; ll = dl[2]; rn = ''; rl = ''; }}
    else {{ ln = ''; ll = ''; rn = dl[1]; rl = dl[2]; }}

    var lc, rc;
    if (s === 'c' && ll && rl) {{
      var wd = wordDiff(ll, rl); lc = wd[0]; rc = wd[1];
    }} else {{
      lc = esc(ll); rc = esc(rl);
    }}

    rows.push('<tr class="' + (STATUS[s]||'diff-equal') + '">' +
      '<td class="line-num">' + (ln||'') + '</td>' +
      '<td class="diff-marker">' + (LM[s]||' ') + '</td>' +
      '<td class="code-cell left">' + lc + '</td>' +
      '<td class="divider"></td>' +
      '<td class="line-num">' + (rn||'') + '</td>' +
      '<td class="diff-marker">' + (RM[s]||' ') + '</td>' +
      '<td class="code-cell right">' + rc + '</td>' +
      '</tr>');
  }}
  return '<table class="diff-table"><tbody>' + rows.join('') + '</tbody></table>';
}}

// ── File view renderer ───────────────────────────────────────────────────

function renderFileCard(fileId, data) {{
  var hasChanges = data.hc;
  var badgeClass = hasChanges ? 'badge-changed' : 'badge-same';
  var badgeText  = hasChanges ? 'CHANGED' : 'NO CHANGES';

  var statsParts = [];
  if (data.fc) statsParts.push(data.fc + ' functions');
  if (data.tc) statsParts.push(data.tc + ' total changes');
  if (data.cf) statsParts.push('confidence: ' + data.cf);
  var statsText = statsParts.join(' · ') || '—';

  var diffHtml = hasChanges
    ? renderDiffTable(data.dl)
    : '<div class="no-changes">No changes — file is already compatible</div>';

  return '<div class="file-card" id="' + fileId + '">' +
    '<div class="file-header">' +
      '<div class="file-info">' +
        '<span class="file-type-badge ' + esc(data.ft) + '">' + esc(data.tl) + '</span>' +
        '<span class="file-name">' + esc(data.fn) + '</span>' +
        '<span class="file-badge ' + badgeClass + '">' + badgeText + '</span>' +
      '</div>' +
      '<div class="file-stats">' + esc(statsText) + '</div>' +
    '</div>' +
    '<div class="diff-labels">' +
      '<div class="diff-label-left">Original (' + esc(SRC) + ')</div>' +
      '<div class="diff-label-right">Converted (' + esc(TGT) + ')</div>' +
    '</div>' +
    '<div class="diff-container">' + diffHtml + '</div>' +
    '</div>';
}}

// ── Navigation ───────────────────────────────────────────────────────────

function selectFile(fileId) {{
  var data = FILES[fileId];
  if (!data) return false;
  document.querySelectorAll('.nav-item').forEach(function(n) {{ n.classList.remove('active'); }});
  var nav = document.querySelector('[data-id="' + fileId + '"]');
  if (nav) nav.classList.add('active');
  document.getElementById('file-view').innerHTML = renderFileCard(fileId, data);
  return false;
}}

function selectGuide() {{
  if (!GUIDELINES) return false;
  document.querySelectorAll('.nav-item').forEach(function(n) {{ n.classList.remove('active'); }});
  var nav = document.querySelector('[data-id="llm-guide"]');
  if (nav) nav.classList.add('active');
  document.getElementById('file-view').innerHTML = GUIDELINES;
  return false;
}}

function filterNav(mode, btn) {{
  document.querySelectorAll('.sidebar-filter .filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
  btn.classList.add('active');
  document.querySelectorAll('.nav-item[data-id]').forEach(function(item) {{
    if (!item.dataset.changed) return;
    var changed = item.dataset.changed === 'true';
    if (mode === 'all') item.style.display = '';
    else if (mode === 'changed') item.style.display = changed ? '' : 'none';
    else item.style.display = changed ? 'none' : '';
  }});
}}

// ── Init ─────────────────────────────────────────────────────────────────

(function() {{
  var first = '{auto_select}';
  if (first && FILES[first]) selectFile(first);
}})();
</script>
</body>
</html>"""
