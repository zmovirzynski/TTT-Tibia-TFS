"""
Review data models — ReviewFinding, ReviewCategory, ReviewReport.
"""

import enum
from dataclasses import dataclass, field
from typing import Dict, List


class ReviewCategory(enum.Enum):
    """Category for grouping review findings."""
    API_REPLACEMENT = "api-replacement"
    OBJECT_UNWRAPPING = "object-unwrapping"
    UNSUPPORTED_LEGACY = "unsupported-legacy"
    CUSTOM_FUNCTION = "custom-function"
    CONFIDENCE_RISK = "confidence-risk"
    GENERAL = "general"


# Display labels for terminal / HTML output
CATEGORY_LABELS = {
    ReviewCategory.API_REPLACEMENT: "API Replacement Needed",
    ReviewCategory.OBJECT_UNWRAPPING: "Object Unwrapping",
    ReviewCategory.UNSUPPORTED_LEGACY: "Unsupported Legacy Behavior",
    ReviewCategory.CUSTOM_FUNCTION: "Custom / Game-Specific Function",
    ReviewCategory.CONFIDENCE_RISK: "Confidence / Risk",
    ReviewCategory.GENERAL: "General Review",
}


@dataclass
class ReviewFinding:
    """A single ``-- TTT:`` marker occurrence."""

    file: str
    line_number: int
    marker_text: str
    category: ReviewCategory
    snippet: str = ""

    @property
    def short_text(self) -> str:
        """Return the marker text without the ``-- TTT:`` prefix."""
        text = self.marker_text
        for prefix in ("-- TTT:STUB:", "-- TTT:"):
            if text.strip().startswith(prefix):
                return text.strip()[len(prefix):].strip()
        return text.strip()


@dataclass
class ReviewReport:
    """Aggregated review report for a set of scanned files."""

    scanned_dir: str = ""
    total_files_scanned: int = 0
    findings: List[ReviewFinding] = field(default_factory=list)

    # ── Grouping helpers ──────────────────────────────────────────────

    @property
    def total_markers(self) -> int:
        return len(self.findings)

    def by_category(self) -> Dict[ReviewCategory, List[ReviewFinding]]:
        groups: Dict[ReviewCategory, List[ReviewFinding]] = {}
        for f in self.findings:
            groups.setdefault(f.category, []).append(f)
        return groups

    def by_file(self) -> Dict[str, List[ReviewFinding]]:
        groups: Dict[str, List[ReviewFinding]] = {}
        for f in self.findings:
            groups.setdefault(f.file, []).append(f)
        return groups

    def top_blockers(self, limit: int = 10) -> List[Dict]:
        """Return files with the most markers, for fastest human triage."""
        file_groups = self.by_file()
        ranked = sorted(file_groups.items(), key=lambda p: len(p[1]), reverse=True)
        result = []
        for path, findings in ranked[:limit]:
            cats = {}
            for f in findings:
                cats[f.category.value] = cats.get(f.category.value, 0) + 1
            result.append({
                "file": path,
                "count": len(findings),
                "categories": cats,
            })
        return result

    def to_dict(self) -> Dict:
        """Serializable dict for JSON export."""
        return {
            "scanned_dir": self.scanned_dir,
            "total_files_scanned": self.total_files_scanned,
            "total_markers": self.total_markers,
            "findings": [
                {
                    "file": f.file,
                    "line": f.line_number,
                    "marker": f.marker_text,
                    "category": f.category.value,
                    "snippet": f.snippet,
                }
                for f in self.findings
            ],
            "by_category": {
                cat.value: len(items)
                for cat, items in self.by_category().items()
            },
            "top_blockers": self.top_blockers(),
        }
