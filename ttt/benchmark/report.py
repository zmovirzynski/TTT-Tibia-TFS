"""
Benchmark report formatters — terminal text and JSON output.
"""

import json
from typing import List

from .models import BenchmarkResult

_SEP = "=" * 64
_THIN = "-" * 64


def format_benchmark_text(results: List[BenchmarkResult]) -> str:
    """Format benchmark results as readable terminal text."""
    lines: List[str] = []
    lines.append("")
    lines.append(_SEP)
    lines.append("  TTT — Benchmark Results")
    lines.append(_SEP)

    for r in results:
        lines.append("")
        lines.append(f"  Corpus: {r.corpus_name}")
        lines.append(f"  {r.source_version} → {r.target_version}")
        lines.append(f"  {_THIN}")
        lines.append(f"  Duration:            {r.duration_seconds:.3f}s")
        lines.append(f"  Files converted:     {r.files_converted}")
        lines.append(f"    Lua files:         {r.lua_files_processed}")
        lines.append(f"    XML files:         {r.xml_files_processed}")
        lines.append(f"  Conversion errors:   {r.conversion_errors}")
        lines.append(f"  Review markers:      {r.review_markers}")
        lines.append(f"  Unrecognized calls:  {r.unrecognized_calls}")
        lines.append(f"  Steps: {r.steps_succeeded} ok / {r.steps_failed} failed")

        if r.golden_comparisons:
            lines.append("")
            lines.append("  Golden Comparisons:")
            lines.append(f"  {_THIN}")
            for g in r.golden_comparisons:
                status = "MATCH" if g.match else f"DIFF ({g.diff_lines} lines)"
                lines.append(f"    {g.file:<40s} {status}")
            rate = r.golden_match_rate * 100
            lines.append(f"  Match rate: {rate:.1f}% ({r.golden_matches}/{len(r.golden_comparisons)})")

        status = "PASS" if r.success else "FAIL"
        lines.append(f"  Status: {status}")
        lines.append("")

    # Aggregate
    if len(results) > 1:
        total_pass = sum(1 for r in results if r.success)
        total_dur = sum(r.duration_seconds for r in results)
        lines.append(_SEP)
        lines.append(f"  Total: {total_pass}/{len(results)} passed in {total_dur:.3f}s")

    lines.append(_SEP)
    lines.append("")
    return "\n".join(lines)


def format_benchmark_json(results: List[BenchmarkResult]) -> str:
    """Serialize benchmark results to JSON."""
    data = {
        "benchmarks": [r.to_dict() for r in results],
        "total": len(results),
        "passed": sum(1 for r in results if r.success),
        "failed": sum(1 for r in results if not r.success),
    }
    return json.dumps(data, indent=2)
