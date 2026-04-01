"""
Benchmark data models — BenchmarkResult, CorpusEntry, GoldenComparison.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass
class GoldenComparison:
    """Result of comparing one converted file against its golden expected output."""
    file: str
    match: bool
    diff_lines: int = 0
    expected_lines: int = 0
    actual_lines: int = 0


@dataclass
class CorpusEntry:
    """A single benchmark corpus entry (input dir + optional golden output dir)."""
    name: str
    input_dir: str
    golden_dir: str = ""
    source_version: str = "tfs03"
    target_version: str = "revscript"


@dataclass
class BenchmarkResult:
    """Full result of running a benchmark against a corpus."""

    corpus_name: str = ""
    source_version: str = ""
    target_version: str = ""

    # Timing
    duration_seconds: float = 0.0

    # Conversion metrics
    files_converted: int = 0
    lua_files_processed: int = 0
    xml_files_processed: int = 0
    conversion_errors: int = 0

    # Quality metrics
    review_markers: int = 0
    unrecognized_calls: int = 0

    # Step success/failure
    steps_run: int = 0
    steps_succeeded: int = 0
    steps_failed: int = 0

    # Golden comparisons
    golden_comparisons: List[GoldenComparison] = field(default_factory=list)
    golden_matches: int = 0
    golden_mismatches: int = 0

    # Raw step outputs for inspection
    step_outputs: Dict[str, Any] = field(default_factory=dict)

    @property
    def golden_match_rate(self) -> float:
        total = len(self.golden_comparisons)
        if total == 0:
            return 1.0
        return self.golden_matches / total

    @property
    def success(self) -> bool:
        return self.conversion_errors == 0 and self.steps_failed == 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "corpus_name": self.corpus_name,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "duration_seconds": round(self.duration_seconds, 3),
            "files_converted": self.files_converted,
            "lua_files_processed": self.lua_files_processed,
            "xml_files_processed": self.xml_files_processed,
            "conversion_errors": self.conversion_errors,
            "review_markers": self.review_markers,
            "unrecognized_calls": self.unrecognized_calls,
            "steps_run": self.steps_run,
            "steps_succeeded": self.steps_succeeded,
            "steps_failed": self.steps_failed,
            "golden_match_rate": round(self.golden_match_rate, 4),
            "golden_matches": self.golden_matches,
            "golden_mismatches": self.golden_mismatches,
            "golden_comparisons": [
                {
                    "file": g.file,
                    "match": g.match,
                    "diff_lines": g.diff_lines,
                }
                for g in self.golden_comparisons
            ],
            "success": self.success,
        }
