"""
Review scanner — Finds and categorizes ``-- TTT:`` markers in Lua files.
"""

import os
import re
from typing import List

from .models import ReviewCategory, ReviewFinding, ReviewReport

# Marker regex: captures everything after ``-- TTT:``
_MARKER_RE = re.compile(r"--\s*TTT:(.*)")

# Categorization rules (checked in order, first match wins)
_CATEGORY_RULES = [
    # STUB markers → custom/game-specific function
    (re.compile(r"STUB:", re.IGNORECASE), ReviewCategory.CUSTOM_FUNCTION),
    # Removed / no equivalent → unsupported legacy
    (re.compile(r"removed|no direct equivalent|no equivalent|deprecated", re.IGNORECASE),
     ReviewCategory.UNSUPPORTED_LEGACY),
    # Object unwrapping hints
    (re.compile(r"auto-chained|unwrap|:get\w+\(\)", re.IGNORECASE),
     ReviewCategory.OBJECT_UNWRAPPING),
    # API replacement hints
    (re.compile(r"\bUse\b|In 1\.x|replace|Combat object|condition system", re.IGNORECASE),
     ReviewCategory.API_REPLACEMENT),
    # Confidence / review hints
    (re.compile(r"Review|verify|check|manual|confidence|risk", re.IGNORECASE),
     ReviewCategory.CONFIDENCE_RISK),
    # Function body not found → custom function
    (re.compile(r"Function body not found", re.IGNORECASE),
     ReviewCategory.CUSTOM_FUNCTION),
]


def categorize_marker(text: str) -> ReviewCategory:
    """Determine the category for a marker based on its text content."""
    for pattern, category in _CATEGORY_RULES:
        if pattern.search(text):
            return category
    return ReviewCategory.GENERAL


class ReviewScanner:
    """Scans a directory tree for ``-- TTT:`` markers and builds a ReviewReport."""

    def __init__(self, context_lines: int = 2):
        self.context_lines = context_lines

    def scan(self, path: str) -> ReviewReport:
        """Scan *path* (file or directory) and return the review report."""
        report = ReviewReport(scanned_dir=path)

        if os.path.isfile(path):
            findings = self._scan_file(path)
            if findings:
                report.findings.extend(findings)
            report.total_files_scanned = 1
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for fname in sorted(files):
                    if not fname.endswith(".lua"):
                        continue
                    fpath = os.path.join(root, fname)
                    report.total_files_scanned += 1
                    findings = self._scan_file(fpath)
                    report.findings.extend(findings)
        return report

    def _scan_file(self, filepath: str) -> List[ReviewFinding]:
        """Scan a single file and return its findings."""
        findings: List[ReviewFinding] = []
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                lines = f.readlines()
        except OSError:
            return findings

        for idx, line in enumerate(lines):
            match = _MARKER_RE.search(line)
            if not match:
                continue

            marker_text = line.rstrip("\n\r")
            rest = match.group(1).strip()
            category = categorize_marker(rest)

            # Build snippet (surrounding context)
            start = max(0, idx - self.context_lines)
            end = min(len(lines), idx + self.context_lines + 1)
            snippet = "".join(lines[start:end])

            # Use path relative to scanned_dir when possible
            rel_path = filepath
            findings.append(
                ReviewFinding(
                    file=rel_path,
                    line_number=idx + 1,
                    marker_text=marker_text,
                    category=category,
                    snippet=snippet.rstrip(),
                )
            )

        return findings

    def scan_with_relative_paths(self, path: str) -> ReviewReport:
        """Scan and normalize file paths to be relative to *path*."""
        report = self.scan(path)
        base = os.path.abspath(path)
        for finding in report.findings:
            abs_f = os.path.abspath(finding.file)
            if abs_f.startswith(base):
                finding.file = os.path.relpath(abs_f, base)
        return report
