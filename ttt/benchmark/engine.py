"""
Benchmark engine — Runs the conversion pipeline on a corpus and collects metrics.
"""

import difflib
import logging
import os
import tempfile
import time
from typing import List

from .models import BenchmarkResult, CorpusEntry, GoldenComparison

logger = logging.getLogger("ttt")


class BenchmarkEngine:
    """Runs a benchmark against one or more corpus entries."""

    def run(self, entry: CorpusEntry) -> BenchmarkResult:
        """Execute the benchmark for a single corpus entry."""
        result = BenchmarkResult(
            corpus_name=entry.name,
            source_version=entry.source_version,
            target_version=entry.target_version,
        )

        if not os.path.isdir(entry.input_dir):
            logger.error(f"Corpus input dir does not exist: {entry.input_dir}")
            result.conversion_errors = 1
            return result

        with tempfile.TemporaryDirectory(prefix="ttt_bench_") as tmp_dir:
            t0 = time.time()
            self._run_conversion(entry, tmp_dir, result)
            result.duration_seconds = time.time() - t0

            # Count review markers in output
            result.review_markers = self._count_markers(tmp_dir)

            # Golden comparison
            if entry.golden_dir and os.path.isdir(entry.golden_dir):
                self._compare_golden(tmp_dir, entry.golden_dir, result)

        return result

    def run_corpus(self, entries: List[CorpusEntry]) -> List[BenchmarkResult]:
        """Run benchmarks for multiple corpus entries."""
        return [self.run(entry) for entry in entries]

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _run_conversion(
        self, entry: CorpusEntry, output_dir: str, result: BenchmarkResult
    ) -> None:
        """Run the ConversionEngine and collect metrics."""
        from ..engine import ConversionEngine

        engine = ConversionEngine(
            source_version=entry.source_version,
            target_version=entry.target_version,
            input_dir=entry.input_dir,
            output_dir=output_dir,
            verbose=False,
            dry_run=False,
            html_diff=False,
        )

        validation_errors = engine.validate()
        if validation_errors:
            result.conversion_errors = len(validation_errors)
            result.steps_run = 1
            result.steps_failed = 1
            return

        stats = engine.run()
        result.steps_run = 1
        result.lua_files_processed = stats.get("lua_files_processed", 0)
        result.xml_files_processed = stats.get("xml_files_processed", 0)
        result.files_converted = result.lua_files_processed + result.xml_files_processed
        result.conversion_errors = stats.get("errors", 0)
        result.unrecognized_calls = stats.get("unrecognized_calls", 0)
        result.step_outputs["convert"] = stats

        if result.conversion_errors == 0:
            result.steps_succeeded = 1
        else:
            result.steps_failed = 1

    def _count_markers(self, output_dir: str) -> int:
        """Count -- TTT: markers in all Lua files under output_dir."""
        total = 0
        if not os.path.isdir(output_dir):
            return total
        for root, _, files in os.walk(output_dir):
            for fname in files:
                if fname.endswith(".lua"):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            total += sum(1 for line in f if "-- TTT:" in line)
                    except OSError:
                        pass
        return total

    def _compare_golden(
        self, actual_dir: str, golden_dir: str, result: BenchmarkResult
    ) -> None:
        """Compare converted output against golden expected files."""
        golden_files = self._collect_lua_files(golden_dir)

        for rel_path in sorted(golden_files):
            golden_path = os.path.join(golden_dir, rel_path)
            actual_path = os.path.join(actual_dir, rel_path)

            try:
                with open(golden_path, "r", encoding="utf-8", errors="ignore") as f:
                    golden_lines = f.readlines()
            except OSError:
                continue

            if not os.path.exists(actual_path):
                result.golden_comparisons.append(
                    GoldenComparison(
                        file=rel_path,
                        match=False,
                        diff_lines=len(golden_lines),
                        expected_lines=len(golden_lines),
                        actual_lines=0,
                    )
                )
                result.golden_mismatches += 1
                continue

            try:
                with open(actual_path, "r", encoding="utf-8", errors="ignore") as f:
                    actual_lines = f.readlines()
            except OSError:
                result.golden_mismatches += 1
                continue

            diff = list(difflib.unified_diff(golden_lines, actual_lines, n=0))
            diff_count = sum(
                1 for line in diff if line.startswith("+") or line.startswith("-")
            )

            is_match = len(diff) == 0
            result.golden_comparisons.append(
                GoldenComparison(
                    file=rel_path,
                    match=is_match,
                    diff_lines=diff_count,
                    expected_lines=len(golden_lines),
                    actual_lines=len(actual_lines),
                )
            )
            if is_match:
                result.golden_matches += 1
            else:
                result.golden_mismatches += 1

    def _collect_lua_files(self, directory: str) -> List[str]:
        """Return relative paths of all .lua files under directory."""
        results = []
        base = os.path.abspath(directory)
        for root, _, files in os.walk(directory):
            for fname in sorted(files):
                if fname.endswith(".lua"):
                    fpath = os.path.join(root, fname)
                    results.append(os.path.relpath(fpath, base))
        return results
