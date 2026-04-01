"""
TTT Analyzer — Server analysis toolkit.

Modules:
  stats            General server statistics
  dead_code        Dead code detector (unused scripts, orphan XML refs)
  duplicates       Duplicate script / registration detector
  storage_scanner  Storage ID scanner and conflict detector
  item_usage       Item ID usage analysis
  complexity       Cyclomatic complexity scorer for Lua
"""

from .stats import collect_stats, ServerStats
from .dead_code import detect_dead_code, DeadCodeReport
from .duplicates import detect_duplicates, DuplicateReport
from .storage_scanner import scan_storage, StorageReport
from .item_usage import scan_item_usage, ItemUsageReport
from .complexity import analyze_complexity, ComplexityReport
from .engine import AnalyzeEngine, AnalysisReport

__all__ = [
    "collect_stats",
    "ServerStats",
    "detect_dead_code",
    "DeadCodeReport",
    "detect_duplicates",
    "DuplicateReport",
    "scan_storage",
    "StorageReport",
    "scan_item_usage",
    "ItemUsageReport",
    "analyze_complexity",
    "ComplexityReport",
    "AnalyzeEngine",
    "AnalysisReport",
]
