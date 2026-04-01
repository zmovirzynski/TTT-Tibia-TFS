"""
TTT Benchmark — Measures conversion quality against curated corpora.

Runs the conversion pipeline on a corpus directory, compares output against
golden expected files, and reports metrics: files converted, review markers,
unrecognized calls, step success/failure, and timing.
"""

from .models import BenchmarkResult, CorpusEntry, GoldenComparison
from .engine import BenchmarkEngine
from .report import format_benchmark_text, format_benchmark_json
from .trend import (
    load_history,
    append_result,
    format_trend_text,
    format_trend_json,
    generate_trend_html,
)

__all__ = [
    "BenchmarkResult",
    "BenchmarkEngine",
    "CorpusEntry",
    "GoldenComparison",
    "format_benchmark_text",
    "format_benchmark_json",
    "load_history",
    "append_result",
    "format_trend_text",
    "format_trend_json",
    "generate_trend_html",
]
