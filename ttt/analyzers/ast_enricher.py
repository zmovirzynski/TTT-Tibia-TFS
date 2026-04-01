"""Enriches LuaFileAnalysis with AST-derived metrics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from ttt.analyzers.lua_oop_analyzer import LuaFileAnalysis

from ttt.converters.ast_complexity import FunctionMetrics, compute_file_complexity
from ttt.converters.ast_dead_code import UnusedLocal, find_unused_locals


@dataclass
class ASTMetrics:
    function_metrics: List[FunctionMetrics] = field(default_factory=list)
    unused_locals: List[UnusedLocal] = field(default_factory=list)

    @property
    def max_complexity(self) -> int:
        if not self.function_metrics:
            return 0
        return max(m.cyclomatic for m in self.function_metrics)

    @property
    def max_nesting(self) -> int:
        if not self.function_metrics:
            return 0
        return max(m.nesting_depth for m in self.function_metrics)

    @property
    def high_complexity_functions(self) -> List[FunctionMetrics]:
        return [m for m in self.function_metrics if m.rating in ("HIGH", "VERY HIGH")]


def enrich_analysis(analysis: "LuaFileAnalysis", code: str) -> "LuaFileAnalysis":
    """Populate analysis.ast_metrics from AST analysis of code.

    Mutates and returns analysis. Never raises.
    """
    fn_metrics = compute_file_complexity(code)
    unused = find_unused_locals(code)
    analysis.ast_metrics = ASTMetrics(
        function_metrics=fn_metrics,
        unused_locals=unused,
    )
    return analysis
