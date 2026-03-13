"""
Conversion report generator.

Produces a detailed conversion_report.txt with:
  - Files processed
  - Functions converted automatically
  - Unrecognized functions
  - Points marked with -- TTT:
  - XML files converted
  - Per-file breakdown
  - Estimated success rate
"""

import os
import re
import time
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass, field


@dataclass
class FileReport:
    source_path: str
    output_path: str = ""
    file_type: str = ""              
    conversion_type: str = ""        
    functions_converted: int = 0
    signatures_updated: int = 0
    constants_replaced: int = 0
    variables_renamed: int = 0
    ttt_warnings: int = 0            
    unrecognized_calls: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    error: str = ""
    success: bool = True
    original_content: str = ""       
    converted_content: str = ""      

    @property
    def total_changes(self) -> int:
        return (self.functions_converted + self.signatures_updated +
                self.constants_replaced + self.variables_renamed)

    @property
    def confidence_score(self) -> float:
        if self.error:
            return 0.0
        if self.total_changes == 0 and self.ttt_warnings == 0:
            return 1.0  # nothing to change or pure copy

        score = 1.0
        # Each TTT warning reduces confidence
        if self.total_changes > 0:
            warning_ratio = self.ttt_warnings / max(self.total_changes, 1)
            score -= min(warning_ratio * 0.3, 0.4)
        # Unrecognized calls reduce confidence
        if self.unrecognized_calls:
            unrec_penalty = len(self.unrecognized_calls) * 0.05
            score -= min(unrec_penalty, 0.3)
        return max(score, 0.1)

    @property
    def confidence_label(self) -> str:
        s = self.confidence_score
        if s >= 0.95:
            return "HIGH"
        elif s >= 0.75:
            return "MEDIUM"
        elif s >= 0.50:
            return "LOW"
        else:
            return "REVIEW"


class ConversionReport:

    def __init__(self, source_version: str, target_version: str,
                 input_dir: str, output_dir: str):
        self.source_version = source_version
        self.target_version = target_version
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.start_time = time.time()
        self.file_reports: List[FileReport] = []
        self.scan_summary: str = ""

        # Global unrecognized function tracker
        self._unrecognized_global: Dict[str, int] = {}

    def add_file_report(self, report: FileReport):
        self.file_reports.append(report)
        for func in report.unrecognized_calls:
            self._unrecognized_global[func] = self._unrecognized_global.get(func, 0) + 1

    def count_ttt_warnings_in_file(self, filepath: str) -> int:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                return sum(1 for line in f if "-- TTT:" in line)
        except Exception:
            return 0

    @property
    def elapsed(self) -> float:
        return time.time() - self.start_time

    # Aggregate stats

    @property
    def total_files(self) -> int:
        return len(self.file_reports)

    @property
    def successful_files(self) -> int:
        return sum(1 for r in self.file_reports if r.success)

    @property
    def failed_files(self) -> int:
        return sum(1 for r in self.file_reports if not r.success)

    @property
    def total_functions_converted(self) -> int:
        return sum(r.functions_converted for r in self.file_reports)

    @property
    def total_signatures_updated(self) -> int:
        return sum(r.signatures_updated for r in self.file_reports)

    @property
    def total_constants_replaced(self) -> int:
        return sum(r.constants_replaced for r in self.file_reports)

    @property
    def total_variables_renamed(self) -> int:
        return sum(r.variables_renamed for r in self.file_reports)

    @property
    def total_ttt_warnings(self) -> int:
        return sum(r.ttt_warnings for r in self.file_reports)

    @property
    def total_changes(self) -> int:
        return sum(r.total_changes for r in self.file_reports)

    @property
    def overall_confidence(self) -> float:
        if not self.file_reports:
            return 1.0
        scores = [r.confidence_score for r in self.file_reports if r.total_changes > 0]
        if not scores:
            return 1.0
        return sum(scores) / len(scores)

    @property
    def overall_confidence_label(self) -> str:
        s = self.overall_confidence
        if s >= 0.95:
            return "HIGH"
        elif s >= 0.75:
            return "MEDIUM"
        elif s >= 0.50:
            return "LOW"
        else:
            return "REVIEW NEEDED"

    @property
    def success_rate(self) -> float:
        if self.total_files == 0:
            return 100.0
        return (self.successful_files / self.total_files) * 100

    def generate(self, output_path: Optional[str] = None) -> str:
        report = self._build_report()
        if output_path:
            os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
        return report

    def _build_report(self) -> str:
        lines = []
        w = lines.append

        w("=" * 72)
        w("  TTT — TFS Script Converter  ·  Conversion Report")
        w("=" * 72)
        w(f"  Date:       {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        w(f"  Source:     {self.source_version}")
        w(f"  Target:     {self.target_version}")
        w(f"  Input:      {self.input_dir}")
        w(f"  Output:     {self.output_dir}")
        w(f"  Duration:   {self.elapsed:.2f}s")
        w("")

        # Overview
        w("-" * 72)
        w("  OVERVIEW")
        w("-" * 72)
        w(f"  Files processed:                {self.total_files}")
        w(f"  Successful conversions:         {self.successful_files}")
        w(f"  Failed conversions:             {self.failed_files}")
        w(f"  Success rate:                   {self.success_rate:.0f}%")
        w("")
        w(f"  Function calls converted:       {self.total_functions_converted}")
        w(f"  Callback signatures updated:    {self.total_signatures_updated}")
        w(f"  Constants replaced:             {self.total_constants_replaced}")
        w(f"  Variables renamed:              {self.total_variables_renamed}")
        w(f"  Total automatic changes:        {self.total_changes}")
        w("")
        w(f"  Points needing review (-- TTT): {self.total_ttt_warnings}")
        w(f"  Estimated confidence:           {self.overall_confidence:.0%} ({self.overall_confidence_label})")
        w("")

        # Per-file
        w("-" * 72)
        w("  PER-FILE BREAKDOWN")
        w("-" * 72)

        for r in self.file_reports:
            src = os.path.relpath(r.source_path, self.input_dir) if self.input_dir else r.source_path
            status = "OK" if r.success else "FAIL"
            conf = r.confidence_label
            w(f"  [{status}] {src}")
            parts = []
            if r.functions_converted:
                parts.append(f"{r.functions_converted} func")
            if r.signatures_updated:
                parts.append(f"{r.signatures_updated} sig")
            if r.constants_replaced:
                parts.append(f"{r.constants_replaced} const")
            if r.variables_renamed:
                parts.append(f"{r.variables_renamed} vars")
            if r.ttt_warnings:
                parts.append(f"{r.ttt_warnings} warnings")

            detail = ", ".join(parts) if parts else "no changes"
            w(f"         → {detail}  [confidence: {conf}]")

            if r.error:
                w(f"         ✗ Error: {r.error}")
            if r.unrecognized_calls:
                funcs = ", ".join(r.unrecognized_calls[:5])
                extra = f" (+{len(r.unrecognized_calls)-5} more)" if len(r.unrecognized_calls) > 5 else ""
                w(f"         ? Unrecognized: {funcs}{extra}")
            w("")


        if self._unrecognized_global:
            w("-" * 72)
            w("  UNRECOGNIZED FUNCTIONS (may need manual conversion)")
            w("-" * 72)
            sorted_funcs = sorted(self._unrecognized_global.items(), key=lambda x: -x[1])
            for func, count in sorted_funcs:
                w(f"    {func:<45s}  ({count}x)")
            w("")

        ttt_files = [r for r in self.file_reports if r.ttt_warnings > 0]
        if ttt_files:
            w("-" * 72)
            w("  FILES WITH -- TTT: REVIEW MARKERS")
            w("-" * 72)
            for r in ttt_files:
                src = os.path.relpath(r.source_path, self.input_dir) if self.input_dir else r.source_path
                w(f"    {src:<45s}  {r.ttt_warnings} marker(s)")
            w("")

        error_files = [r for r in self.file_reports if r.error]
        if error_files:
            w("-" * 72)
            w("  ERRORS")
            w("-" * 72)
            for r in error_files:
                src = os.path.relpath(r.source_path, self.input_dir) if self.input_dir else r.source_path
                w(f"    {src}")
                w(f"      → {r.error}")
            w("")

        w("=" * 72)
        w("  Generated by TTT — TFS Script Converter v2.0")
        w("  Review files marked with '-- TTT:' comments before use in production.")
        w("=" * 72)

        return "\n".join(lines) + "\n"

    def generate_dry_run(self) -> str:
        lines = []
        w = lines.append

        w("=" * 72)
        w("  TTT — DRY RUN ANALYSIS (no files written)")
        w("=" * 72)
        w(f"  Source:     {self.source_version}")
        w(f"  Target:     {self.target_version}")
        w(f"  Input:      {self.input_dir}")
        w("")

        if self.scan_summary:
            w("-" * 72)
            w("  DETECTED STRUCTURE")
            w("-" * 72)
            for line in self.scan_summary.split("\n"):
                w(f"  {line}")
            w("")


        convertible = [r for r in self.file_reports if r.success and r.total_changes > 0]
        copy_only = [r for r in self.file_reports if r.success and r.total_changes == 0 and not r.error]
        will_fail = [r for r in self.file_reports if not r.success or r.error]
        needs_review = [r for r in self.file_reports if r.ttt_warnings > 0 or r.unrecognized_calls]

        w("-" * 72)
        w("  CONVERSION PREVIEW")
        w("-" * 72)
        w(f"  Files that CAN be converted:    {len(convertible)}")
        w(f"  Files copied as-is:             {len(copy_only)}")
        w(f"  Files that will need review:    {len(needs_review)}")
        w(f"  Files with errors:              {len(will_fail)}")
        w("")
        w(f"  Estimated changes:")
        w(f"    Function calls:               {self.total_functions_converted}")
        w(f"    Callback signatures:          {self.total_signatures_updated}")
        w(f"    Constants:                    {self.total_constants_replaced}")
        w(f"    Variables:                    {self.total_variables_renamed}")
        w(f"    Total automatic changes:      {self.total_changes}")
        w("")
        w(f"  Estimated confidence:           {self.overall_confidence:.0%} ({self.overall_confidence_label})")
        w("")


        if convertible:
            w("-" * 72)
            w("  FILES THAT WILL BE CONVERTED")
            w("-" * 72)
            for r in convertible:
                src = os.path.relpath(r.source_path, self.input_dir)
                conf = r.confidence_label
                w(f"    {src:<45s}  [{conf}]")
            w("")

        if needs_review:
            w("-" * 72)
            w("  FILES THAT WILL NEED MANUAL REVIEW")
            w("-" * 72)
            for r in needs_review:
                src = os.path.relpath(r.source_path, self.input_dir)
                reasons = []
                if r.ttt_warnings:
                    reasons.append(f"{r.ttt_warnings} ambiguous conversion(s)")
                if r.unrecognized_calls:
                    reasons.append(f"{len(r.unrecognized_calls)} unknown function(s)")
                w(f"    {src}")
                w(f"      → {'; '.join(reasons)}")
            w("")

        if self._unrecognized_global:
            w("-" * 72)
            w("  UNRECOGNIZED FUNCTIONS FOUND")
            w("-" * 72)
            sorted_funcs = sorted(self._unrecognized_global.items(), key=lambda x: -x[1])
            for func, count in sorted_funcs[:20]:
                w(f"    {func:<45s}  ({count}x)")
            if len(self._unrecognized_global) > 20:
                w(f"    ... and {len(self._unrecognized_global) - 20} more")
            w("")

        w("=" * 72)
        w("  Run without --dry-run to perform the conversion.")
        w("=" * 72)

        return "\n".join(lines) + "\n"
