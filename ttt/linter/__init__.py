"""
TTT Linter — Static analyzer for OTServ/TFS Lua scripts.

Detects deprecated APIs, bad practices, unused parameters,
missing returns, and other common issues in TFS scripts.

Usage:
    from ttt.linter import LintEngine
    engine = LintEngine()
    results = engine.lint_file("path/to/script.lua")
"""

from .engine import LintEngine
from .rules import LintSeverity, LintIssue

__all__ = ["LintEngine", "LintSeverity", "LintIssue"]
