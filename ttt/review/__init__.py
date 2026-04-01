"""
TTT Review — Aggregates and categorizes residual review markers.

Scans converted Lua scripts for ``-- TTT:`` markers, groups findings
by category, and generates terminal, HTML, and JSON reports.
"""

from .models import ReviewFinding, ReviewCategory, ReviewReport
from .scanner import ReviewScanner
from .report import (
    format_review_text,
    format_review_html,
    format_review_json,
)

__all__ = [
    "ReviewFinding",
    "ReviewCategory",
    "ReviewReport",
    "ReviewScanner",
    "format_review_text",
    "format_review_html",
    "format_review_json",
]
