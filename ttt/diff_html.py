"""
HTML Diff Generator.

Generates a standalone HTML page with side-by-side visual diffs
of original vs converted scripts. Includes:
  - Dark themed UI with Lua syntax-aware highlighting
  - File navigation sidebar
  - Line-by-line diff (additions, removals, changes)
  - Conversion summary and stats
  - Zero external dependencies (self-contained HTML/CSS/JS)
"""

import os
import difflib
import html
import time
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


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

    def __init__(self, source_version: str, target_version: str,
                 input_dir: str, output_dir: str):
        self.source_version = source_version
        self.target_version = target_version
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.entries: List[DiffEntry] = []

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

    def _compute_diff_lines(self, original: str, converted: str) -> List[dict]:
        """Calcula diff lado a lado. Retorna lista de dicts (left/right + status)."""
        orig_lines = original.splitlines()
        conv_lines = converted.splitlines()

        matcher = difflib.SequenceMatcher(None, orig_lines, conv_lines)
        result = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                for i, j in zip(range(i1, i2), range(j1, j2)):
                    result.append({
                        "left_num": i + 1,
                        "left_line": orig_lines[i],
                        "right_num": j + 1,
                        "right_line": conv_lines[j],
                        "status": "equal",
                    })
            elif tag == "replace":
                max_len = max(i2 - i1, j2 - j1)
                for k in range(max_len):
                    left_idx = i1 + k if k < (i2 - i1) else None
                    right_idx = j1 + k if k < (j2 - j1) else None
                    result.append({
                        "left_num": (left_idx + 1) if left_idx is not None else "",
                        "left_line": orig_lines[left_idx] if left_idx is not None else "",
                        "right_num": (right_idx + 1) if right_idx is not None else "",
                        "right_line": conv_lines[right_idx] if right_idx is not None else "",
                        "status": "change",
                    })
            elif tag == "delete":
                for i in range(i1, i2):
                    result.append({
                        "left_num": i + 1,
                        "left_line": orig_lines[i],
                        "right_num": "",
                        "right_line": "",
                        "status": "remove",
                    })
            elif tag == "insert":
                for j in range(j1, j2):
                    result.append({
                        "left_num": "",
                        "left_line": "",
                        "right_num": j + 1,
                        "right_line": conv_lines[j],
                        "status": "add",
                    })

        return result

    def _build_html(self) -> str:
        # Compute stats
        total_files = len(self.entries)
        files_changed = sum(1 for e in self.entries if e.original != e.converted)
        total_funcs = sum(e.functions_converted for e in self.entries)
        total_changes = sum(e.total_changes for e in self.entries)

        # Build file cards
        file_cards_html = []
        nav_items_html = []

        for idx, entry in enumerate(self.entries):
            file_id = f"file-{idx}"
            has_changes = entry.original != entry.converted
            badge_class = "badge-changed" if has_changes else "badge-same"
            badge_text = "CHANGED" if has_changes else "NO CHANGES"

            # Navigation item
            type_label = entry.file_type.upper() if entry.file_type else "LUA"
            nav_items_html.append(
                f'<a href="#{file_id}" class="nav-item" data-target="{file_id}">'
                f'<span class="nav-type {entry.file_type}">{_esc(type_label)}</span>'
                f'<span class="nav-name">{_esc(entry.filename)}</span>'
                f'<span class="nav-badge {badge_class}">{badge_text}</span>'
                f'</a>'
            )

            # Diff content
            if has_changes:
                diff_lines = self._compute_diff_lines(entry.original, entry.converted)
                diff_html = self._render_diff_table(diff_lines)
            else:
                diff_html = '<div class="no-changes">No changes — file is already compatible</div>'

            # Stats for this file
            stats_parts = []
            if entry.functions_converted:
                stats_parts.append(f"{entry.functions_converted} functions")
            if entry.total_changes:
                stats_parts.append(f"{entry.total_changes} total changes")
            if entry.confidence:
                stats_parts.append(f"confidence: {entry.confidence}")

            stats_text = " · ".join(stats_parts) if stats_parts else "—"

            file_cards_html.append(f'''
            <div class="file-card" id="{file_id}">
                <div class="file-header">
                    <div class="file-info">
                        <span class="file-type-badge {entry.file_type}">{_esc(type_label)}</span>
                        <span class="file-name">{_esc(entry.filename)}</span>
                        <span class="file-badge {badge_class}">{badge_text}</span>
                    </div>
                    <div class="file-stats">{_esc(stats_text)}</div>
                </div>
                <div class="diff-labels">
                    <div class="diff-label-left">Original ({_esc(self.source_version)})</div>
                    <div class="diff-label-right">Converted ({_esc(self.target_version)})</div>
                </div>
                <div class="diff-container">
                    {diff_html}
                </div>
            </div>
            ''')

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

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
            file_cards="\n".join(file_cards_html),
        )

    def _render_diff_table(self, diff_lines: List[dict]) -> str:
        rows = []
        for line in diff_lines:
            status = line["status"]
            left_num = line["left_num"]
            right_num = line["right_num"]
            left_code = _esc(line["left_line"]) if line["left_line"] else ""
            right_code = _esc(line["right_line"]) if line["right_line"] else ""

            # Apply inline word-level highlighting for changes
            if status == "change" and left_code and right_code:
                left_code, right_code = self._highlight_word_diff(
                    line["left_line"], line["right_line"]
                )

            row_class = f"diff-{status}"
            left_marker = {"equal": " ", "change": "~", "remove": "-", "add": " "}.get(status, " ")
            right_marker = {"equal": " ", "change": "~", "add": "+", "remove": " "}.get(status, " ")

            rows.append(
                f'<tr class="{row_class}">'
                f'<td class="line-num">{left_num}</td>'
                f'<td class="diff-marker">{left_marker}</td>'
                f'<td class="code-cell left">{left_code}</td>'
                f'<td class="divider"></td>'
                f'<td class="line-num">{right_num}</td>'
                f'<td class="diff-marker">{right_marker}</td>'
                f'<td class="code-cell right">{right_code}</td>'
                f'</tr>'
            )

        return f'<table class="diff-table"><tbody>{"".join(rows)}</tbody></table>'

    def _highlight_word_diff(self, left: str, right: str) -> Tuple[str, str]:
        left_tokens = _tokenize(left)
        right_tokens = _tokenize(right)

        matcher = difflib.SequenceMatcher(None, left_tokens, right_tokens)

        left_parts = []
        right_parts = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                left_parts.append(_esc("".join(left_tokens[i1:i2])))
                right_parts.append(_esc("".join(right_tokens[j1:j2])))
            elif tag == "replace":
                left_parts.append(f'<span class="word-del">{_esc("".join(left_tokens[i1:i2]))}</span>')
                right_parts.append(f'<span class="word-add">{_esc("".join(right_tokens[j1:j2]))}</span>')
            elif tag == "delete":
                left_parts.append(f'<span class="word-del">{_esc("".join(left_tokens[i1:i2]))}</span>')
            elif tag == "insert":
                right_parts.append(f'<span class="word-add">{_esc("".join(right_tokens[j1:j2]))}</span>')

        return "".join(left_parts), "".join(right_parts)


def _esc(text: str) -> str:
    return html.escape(str(text))


def _tokenize(text: str) -> List[str]:
    import re
    return re.findall(r'\S+|\s+', text)


_HTML_TEMPLATE = '''<!DOCTYPE html>
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

body {{
    background: var(--bg-dark);
    color: var(--text);
    font-family: var(--font-sans);
    line-height: 1.5;
}}

/* ── Layout ──────────────────────────────── */
.layout {{
    display: flex;
    min-height: 100vh;
}}

.sidebar {{
    width: 280px;
    min-width: 280px;
    background: var(--bg-sidebar);
    border-right: 1px solid var(--border);
    display: flex;
    flex-direction: column;
    position: sticky;
    top: 0;
    height: 100vh;
    overflow-y: auto;
}}

.main {{
    flex: 1;
    padding: 24px;
    overflow-x: auto;
    min-width: 0;
}}

/* ── Sidebar ─────────────────────────────── */
.sidebar-header {{
    padding: 20px 16px;
    border-bottom: 1px solid var(--border);
}}

.sidebar-header h1 {{
    font-size: 16px;
    font-weight: 600;
    color: var(--accent);
    margin-bottom: 4px;
}}

.sidebar-header .subtitle {{
    font-size: 12px;
    color: var(--text-muted);
}}

.sidebar-stats {{
    padding: 12px 16px;
    border-bottom: 1px solid var(--border);
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 8px;
}}

.stat-box {{
    background: var(--bg-card);
    border-radius: 6px;
    padding: 8px 10px;
    text-align: center;
}}

.stat-value {{
    font-size: 20px;
    font-weight: 700;
    color: var(--accent);
    display: block;
}}

.stat-label {{
    font-size: 10px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.sidebar-nav {{
    flex: 1;
    overflow-y: auto;
    padding: 8px 0;
}}

.sidebar-nav-title {{
    padding: 8px 16px 4px;
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}}

.nav-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 16px;
    text-decoration: none;
    color: var(--text);
    font-size: 13px;
    border-left: 2px solid transparent;
    transition: all 0.15s;
}}
.nav-item:hover {{
    background: var(--bg-card);
    border-left-color: var(--accent);
}}
.nav-item.active {{
    background: var(--accent-dim);
    border-left-color: var(--accent);
}}

.nav-type {{
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    background: #30363d;
    color: var(--text-muted);
    padding: 1px 5px;
    border-radius: 3px;
    min-width: 40px;
    text-align: center;
    flex-shrink: 0;
}}
.nav-type.action {{ background: #1a3a2a; color: #3fb950; }}
.nav-type.movement {{ background: #2a2000; color: #d29922; }}
.nav-type.talkaction {{ background: #1a1a3a; color: #8b8bff; }}
.nav-type.creaturescript {{ background: #3a1a2a; color: #f85149; }}
.nav-type.globalevent {{ background: #1a2a3a; color: #58a6ff; }}
.nav-type.npc {{ background: #2a1a3a; color: #bc8cff; }}

.nav-name {{
    flex: 1;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}

.nav-badge, .file-badge {{
    font-size: 9px;
    font-weight: 600;
    padding: 1px 6px;
    border-radius: 10px;
    flex-shrink: 0;
}}
.badge-changed {{
    background: #d292221a;
    color: #d29922;
    border: 1px solid #d2992233;
}}
.badge-same {{
    background: #3fb9501a;
    color: #3fb950;
    border: 1px solid #3fb95033;
}}

/* ── Main content ────────────────────────── */
.page-header {{
    margin-bottom: 24px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--border);
}}
.page-header h2 {{
    font-size: 22px;
    font-weight: 600;
    margin-bottom: 4px;
}}
.page-header p {{
    color: var(--text-muted);
    font-size: 13px;
}}

.summary-row {{
    display: flex;
    gap: 12px;
    margin-bottom: 24px;
    flex-wrap: wrap;
}}

.summary-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 16px 20px;
    flex: 1;
    min-width: 140px;
}}
.summary-card .label {{
    font-size: 11px;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.summary-card .value {{
    font-size: 28px;
    font-weight: 700;
    color: var(--accent);
    margin-top: 2px;
}}

/* ── File cards ──────────────────────────── */
.file-card {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    border-radius: 8px;
    margin-bottom: 20px;
    overflow: hidden;
}}

.file-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 12px 16px;
    background: var(--bg-header);
    border-bottom: 1px solid var(--border);
    flex-wrap: wrap;
    gap: 8px;
}}

.file-info {{
    display: flex;
    align-items: center;
    gap: 8px;
}}

.file-type-badge {{
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    background: #30363d;
    color: var(--text-muted);
    padding: 2px 8px;
    border-radius: 4px;
}}
.file-type-badge.action {{ background: #1a3a2a; color: #3fb950; }}
.file-type-badge.movement {{ background: #2a2000; color: #d29922; }}
.file-type-badge.talkaction {{ background: #1a1a3a; color: #8b8bff; }}
.file-type-badge.creaturescript {{ background: #3a1a2a; color: #f85149; }}
.file-type-badge.globalevent {{ background: #1a2a3a; color: #58a6ff; }}
.file-type-badge.npc {{ background: #2a1a3a; color: #bc8cff; }}

.file-name {{
    font-size: 14px;
    font-weight: 600;
    font-family: var(--font-mono);
}}

.file-stats {{
    font-size: 12px;
    color: var(--text-muted);
}}

.diff-labels {{
    display: flex;
    border-bottom: 1px solid var(--border);
}}
.diff-label-left, .diff-label-right {{
    flex: 1;
    padding: 6px 16px;
    font-size: 11px;
    font-weight: 600;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}
.diff-label-left {{
    border-right: 1px solid var(--border);
    background: #2d12140a;
}}
.diff-label-right {{
    background: #12261e0a;
}}

.diff-container {{
    overflow-x: auto;
}}

.no-changes {{
    padding: 32px;
    text-align: center;
    color: var(--text-muted);
    font-style: italic;
}}

/* ── Diff table ──────────────────────────── */
.diff-table {{
    width: 100%;
    border-collapse: collapse;
    font-family: var(--font-mono);
    font-size: 12.5px;
    line-height: 1.5;
    table-layout: fixed;
}}

.diff-table td {{
    padding: 0 8px;
    vertical-align: top;
    white-space: pre;
    overflow: hidden;
}}

.diff-table .line-num {{
    width: 42px;
    min-width: 42px;
    text-align: right;
    color: var(--text-muted);
    user-select: none;
    opacity: 0.5;
    font-size: 11px;
    padding-right: 6px;
}}

.diff-table .diff-marker {{
    width: 14px;
    min-width: 14px;
    text-align: center;
    color: var(--text-muted);
    user-select: none;
    font-weight: 700;
}}

.diff-table .code-cell {{
    width: calc(50% - 56px);
}}

.diff-table .code-cell.left {{
    border-right: none;
}}

.diff-table .divider {{
    width: 1px;
    min-width: 1px;
    background: var(--border);
    padding: 0;
}}

/* Diff row states */
.diff-equal .code-cell {{ background: transparent; }}

.diff-change .code-cell.left {{
    background: var(--red-bg);
}}
.diff-change .code-cell.right {{
    background: var(--green-bg);
}}
.diff-change .diff-marker {{ color: #d29922; }}

.diff-remove .code-cell.left {{
    background: var(--red-bg);
}}
.diff-remove .diff-marker {{ color: #f85149; }}

.diff-add .code-cell.right {{
    background: var(--green-bg);
}}
.diff-add .diff-marker {{ color: #3fb950; }}

/* Word-level highlights */
.word-del {{
    background: var(--red-word);
    border-radius: 2px;
    padding: 0 1px;
}}
.word-add {{
    background: var(--green-word);
    border-radius: 2px;
    padding: 0 1px;
}}

/* ── Filter bar ──────────────────────────── */
.filter-bar {{
    margin-bottom: 16px;
    display: flex;
    gap: 8px;
    align-items: center;
}}

.filter-btn {{
    background: var(--bg-card);
    border: 1px solid var(--border);
    color: var(--text-muted);
    padding: 6px 14px;
    border-radius: 6px;
    cursor: pointer;
    font-size: 12px;
    font-family: var(--font-sans);
    transition: all 0.15s;
}}
.filter-btn:hover {{
    border-color: var(--accent);
    color: var(--text);
}}
.filter-btn.active {{
    background: var(--accent-dim);
    border-color: var(--accent);
    color: var(--accent);
}}

/* ── Footer ──────────────────────────────── */
.footer {{
    margin-top: 32px;
    padding-top: 16px;
    border-top: 1px solid var(--border);
    text-align: center;
    color: var(--text-muted);
    font-size: 12px;
}}

/* ── Responsive ──────────────────────────── */
@media (max-width: 900px) {{
    .sidebar {{ display: none; }}
    .main {{ padding: 12px; }}
}}
</style>
</head>
<body>
<div class="layout">
    <!-- Sidebar -->
    <aside class="sidebar">
        <div class="sidebar-header">
            <h1>TTT — Visual Diff</h1>
            <div class="subtitle">{source_version} → {target_version}</div>
        </div>

        <div class="sidebar-stats">
            <div class="stat-box">
                <span class="stat-value">{total_files}</span>
                <span class="stat-label">Files</span>
            </div>
            <div class="stat-box">
                <span class="stat-value">{files_changed}</span>
                <span class="stat-label">Changed</span>
            </div>
            <div class="stat-box">
                <span class="stat-value">{total_funcs}</span>
                <span class="stat-label">Functions</span>
            </div>
            <div class="stat-box">
                <span class="stat-value">{total_changes}</span>
                <span class="stat-label">Changes</span>
            </div>
        </div>

        <div class="sidebar-nav">
            <div class="sidebar-nav-title">Files</div>
            {nav_items}
        </div>
    </aside>

    <!-- Main content -->
    <main class="main">
        <div class="page-header">
            <h2>Conversion Diff Report</h2>
            <p>{source_version} → {target_version} · {date} · Input: {input_dir}</p>
        </div>

        <div class="summary-row">
            <div class="summary-card">
                <div class="label">Files Analyzed</div>
                <div class="value">{total_files}</div>
            </div>
            <div class="summary-card">
                <div class="label">Files Changed</div>
                <div class="value">{files_changed}</div>
            </div>
            <div class="summary-card">
                <div class="label">Functions Converted</div>
                <div class="value">{total_funcs}</div>
            </div>
            <div class="summary-card">
                <div class="label">Total Changes</div>
                <div class="value">{total_changes}</div>
            </div>
        </div>

        <div class="filter-bar">
            <button class="filter-btn active" onclick="filterFiles('all')">All</button>
            <button class="filter-btn" onclick="filterFiles('changed')">Changed only</button>
            <button class="filter-btn" onclick="filterFiles('same')">No changes</button>
        </div>

        {file_cards}

        <div class="footer">
            Generated by TTT — TFS Script Converter v2.0 · {date}
        </div>
    </main>
</div>

<script>
// Sidebar navigation highlight
document.querySelectorAll('.nav-item').forEach(function(item) {{
    item.addEventListener('click', function() {{
        document.querySelectorAll('.nav-item').forEach(function(n) {{ n.classList.remove('active'); }});
        this.classList.add('active');
    }});
}});

// Filter buttons
function filterFiles(mode) {{
    document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }});
    event.target.classList.add('active');

    document.querySelectorAll('.file-card').forEach(function(card) {{
        var badge = card.querySelector('.file-badge');
        if (!badge) {{ card.style.display = ''; return; }}
        var isChanged = badge.classList.contains('badge-changed');

        if (mode === 'all') {{
            card.style.display = '';
        }} else if (mode === 'changed') {{
            card.style.display = isChanged ? '' : 'none';
        }} else if (mode === 'same') {{
            card.style.display = isChanged ? 'none' : '';
        }}
    }});
}}

// Highlight active section on scroll
var observer = new IntersectionObserver(function(entries) {{
    entries.forEach(function(entry) {{
        if (entry.isIntersecting) {{
            var id = entry.target.id;
            document.querySelectorAll('.nav-item').forEach(function(n) {{
                n.classList.toggle('active', n.getAttribute('data-target') === id);
            }});
        }}
    }});
}}, {{ threshold: 0.3 }});

document.querySelectorAll('.file-card').forEach(function(card) {{
    observer.observe(card);
}});
</script>
</body>
</html>'''
