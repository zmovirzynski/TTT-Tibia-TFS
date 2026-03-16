"""
TTT Docs Generator — Generates automatic documentation for OTServ servers.

Scans XML and Lua files, extracts registrations and metadata,
then exports to Markdown, HTML (static site), or JSON.
"""

from .generator import (
    DocsGenerator,
    DocEntry,
    DocsReport,
)
from .exporter import (
    export_markdown,
    export_html,
    export_json,
    format_docs_text,
)

__all__ = [
    "DocsGenerator",
    "DocEntry",
    "DocsReport",
    "export_markdown",
    "export_html",
    "export_json",
    "format_docs_text",
]
