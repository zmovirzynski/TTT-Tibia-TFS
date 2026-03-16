"""
Docs exporter — Exports DocsReport to Markdown, HTML (static site), or JSON.

Formats:
  - markdown: One .md file per category + index.md
  - html: Full static site with embedded CSS, nav, detail pages
  - json: Single JSON file (API consumable)
"""

import json
import os
import logging
from typing import Optional

from .generator import DocsReport, DocEntry
from . import templates as tpl

logger = logging.getLogger("ttt")


# ---------------------------------------------------------------------------
# Markdown exporter
# ---------------------------------------------------------------------------

def export_markdown(report: DocsReport, output_dir: str) -> list:
    """Export documentation as Markdown files. Returns list of written paths."""
    os.makedirs(output_dir, exist_ok=True)
    written = []

    # Index
    index_lines = [
        f"# Server Documentation",
        "",
        f"Directory: `{report.directory}`",
        "",
        f"**Total entries:** {report.total_entries}",
        "",
        "## Categories",
        "",
    ]
    for cat_name, entries in report.categories.items():
        if entries:
            title = cat_name.replace("scripts", " Scripts").replace("events", " Events").title()
            index_lines.append(f"- [{title}]({cat_name}.md) ({len(entries)} entries)")
    index_lines.append("")

    index_path = os.path.join(output_dir, "index.md")
    _write(index_path, "\n".join(index_lines))
    written.append(index_path)

    # Category files
    for cat_name, entries in report.categories.items():
        if not entries:
            continue
        title = cat_name.replace("scripts", " Scripts").replace("events", " Events").title()
        lines = [f"# {title}", "", f"{len(entries)} entries", ""]

        # Table header
        cols = _md_columns(cat_name)
        header = "| Name | Script |"
        sep = "|------|--------|"
        for col_label, _ in cols:
            header += f" {col_label} |"
            sep += "------|"
        header += " Description |"
        sep += "-------------|"
        lines.append(header)
        lines.append(sep)

        for entry in entries:
            row = f"| {_md_esc(entry.name)} | {_md_esc(entry.script)} |"
            for _, attr_key in cols:
                val = entry.attributes.get(attr_key, "")
                row += f" {_md_esc(str(val))} |"
            desc = entry.description[:80].replace("|", "\\|")
            row += f" {desc} |"
            lines.append(row)

        lines.append("")

        # Script details
        for entry in entries:
            if entry.lua_content:
                lines.append(f"### {_md_esc(entry.name)}")
                lines.append("")
                if entry.attributes:
                    for k, v in entry.attributes.items():
                        lines.append(f"- **{k}:** {_md_esc(str(v))}")
                    lines.append("")
                lines.append("```lua")
                lines.append(entry.lua_content.rstrip())
                lines.append("```")
                lines.append("")

        cat_path = os.path.join(output_dir, f"{cat_name}.md")
        _write(cat_path, "\n".join(lines))
        written.append(cat_path)

    return written


def _md_columns(category: str):
    """Extra columns for MD table by category."""
    if category == "actions":
        return [("Item ID", "itemid"), ("Action ID", "actionid")]
    elif category == "movements":
        return [("Type", "type")]
    elif category == "talkactions":
        return [("Words", "words")]
    elif category == "creaturescripts":
        return [("Event", "type")]
    elif category == "globalevents":
        return [("Type", "type")]
    elif category == "npcs":
        return [("Keywords", "keywords")]
    elif category == "spells":
        return [("Mana", "mana"), ("Level", "lvl")]
    return []


def _md_esc(text: str) -> str:
    """Escape Markdown special characters in table cells."""
    return text.replace("|", "\\|").replace("\n", " ")


# ---------------------------------------------------------------------------
# HTML exporter
# ---------------------------------------------------------------------------

def export_html(report: DocsReport, output_dir: str) -> list:
    """Export documentation as static HTML site. Returns list of written paths."""
    os.makedirs(output_dir, exist_ok=True)
    written = []

    # Index page
    index_path = os.path.join(output_dir, "index.html")
    _write(index_path, tpl.render_index(report))
    written.append(index_path)

    # Category pages
    for cat_name, entries in report.categories.items():
        if not entries:
            continue
        cat_path = os.path.join(output_dir, f"{cat_name}.html")
        _write(cat_path, tpl.render_category(cat_name, entries))
        written.append(cat_path)

        # Detail pages
        for entry in entries:
            detail_name = tpl._safe_filename(entry.category, entry.name)
            detail_path = os.path.join(output_dir, f"detail_{detail_name}.html")
            _write(detail_path, tpl.render_detail(entry))
            written.append(detail_path)

    return written


# ---------------------------------------------------------------------------
# JSON exporter
# ---------------------------------------------------------------------------

def export_json(report: DocsReport, output_path: Optional[str] = None) -> str:
    """Export documentation as JSON. Returns JSON string. If output_path, also writes file."""
    data = report.as_dict()
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        _write(output_path, json_str)
    return json_str


# ---------------------------------------------------------------------------
# Markdown single-string (for terminal output)
# ---------------------------------------------------------------------------

def format_docs_text(report: DocsReport, no_color: bool = False) -> str:
    """Format docs report as colored text for terminal display."""
    C = _Colors
    if no_color:
        for attr in dir(C):
            if not attr.startswith("_"):
                setattr(C, attr, "")

    lines = []
    _sep = "=" * 60

    lines.append("")
    lines.append(f"  {C.BOLD}TTT Server Documentation{C.RESET}")
    lines.append(f"  {_sep}")
    lines.append(f"  Directory: {C.CYAN}{report.directory}{C.RESET}")
    lines.append(f"  Total entries: {C.BOLD}{report.total_entries}{C.RESET}")
    lines.append("")

    for cat_name, entries in report.categories.items():
        if not entries:
            continue
        title = cat_name.replace("scripts", " Scripts").replace("events", " Events").title()
        lines.append(f"  {C.BOLD}{C.BLUE}{title}{C.RESET} ({len(entries)})")
        lines.append(f"  {'-' * 58}")
        for entry in entries:
            desc_part = f"  {C.DIM}{entry.description[:60]}{C.RESET}" if entry.description else ""
            lines.append(f"    {C.GREEN}{entry.name:<30s}{C.RESET} {entry.script}{desc_part}")
        lines.append("")

    return "\n".join(lines)


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write(path: str, content: str):
    """Write content to file."""
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)
