"""
Cyclomatic complexity analyzer for Lua scripts.

Computes:
  - Cyclomatic complexity per function
  - Max nesting depth
  - Lines of code per function
  - Overall file complexity score
  - Refactoring suggestions for complex scripts
"""

import re
from dataclasses import dataclass, field
from typing import Dict, List

from ..utils import read_file_safe, find_lua_files


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class FunctionComplexity:
    """Complexity metrics for a single function."""

    name: str
    filepath: str
    start_line: int
    end_line: int
    lines_of_code: int
    cyclomatic: int
    max_nesting: int
    suggestion: str = ""

    @property
    def rating(self) -> str:
        """Rate complexity: LOW / MEDIUM / HIGH / VERY HIGH."""
        if self.cyclomatic <= 5:
            return "LOW"
        elif self.cyclomatic <= 10:
            return "MEDIUM"
        elif self.cyclomatic <= 20:
            return "HIGH"
        return "VERY HIGH"


@dataclass
class FileComplexity:
    """Complexity metrics for a whole file."""

    filepath: str
    functions: List[FunctionComplexity] = field(default_factory=list)
    total_lines: int = 0
    code_lines: int = 0

    @property
    def avg_cyclomatic(self) -> float:
        if not self.functions:
            return 0.0
        return sum(f.cyclomatic for f in self.functions) / len(self.functions)

    @property
    def max_cyclomatic(self) -> int:
        if not self.functions:
            return 0
        return max(f.cyclomatic for f in self.functions)

    @property
    def rating(self) -> str:
        mc = self.max_cyclomatic
        if mc <= 5:
            return "LOW"
        elif mc <= 10:
            return "MEDIUM"
        elif mc <= 20:
            return "HIGH"
        return "VERY HIGH"


@dataclass
class ComplexityReport:
    """Aggregated complexity analysis for all files."""

    files: List[FileComplexity] = field(default_factory=list)
    total_functions: int = 0
    total_scripts_scanned: int = 0

    @property
    def avg_complexity(self) -> float:
        all_funcs = [f for fc in self.files for f in fc.functions]
        if not all_funcs:
            return 0.0
        return sum(f.cyclomatic for f in all_funcs) / len(all_funcs)

    @property
    def overall_rating(self) -> str:
        avg = self.avg_complexity
        if avg <= 5:
            return "LOW"
        elif avg <= 10:
            return "MEDIUM"
        elif avg <= 20:
            return "HIGH"
        return "VERY HIGH"

    def complex_functions(self, min_complexity: int = 10) -> List[FunctionComplexity]:
        """Return functions exceeding a complexity threshold."""
        result = []
        for fc in self.files:
            for f in fc.functions:
                if f.cyclomatic >= min_complexity:
                    result.append(f)
        result.sort(key=lambda f: f.cyclomatic, reverse=True)
        return result

    @property
    def distribution(self) -> Dict[str, int]:
        """Distribution of functions by complexity rating."""
        dist = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "VERY HIGH": 0}
        for fc in self.files:
            for f in fc.functions:
                dist[f.rating] += 1
        return dist

    def as_dict(self) -> Dict:
        return {
            "total_functions": self.total_functions,
            "total_scripts_scanned": self.total_scripts_scanned,
            "avg_complexity": round(self.avg_complexity, 2),
            "overall_rating": self.overall_rating,
            "distribution": self.distribution,
            "complex_functions": [
                {
                    "name": f.name,
                    "filepath": f.filepath,
                    "line": f.start_line,
                    "cyclomatic": f.cyclomatic,
                    "max_nesting": f.max_nesting,
                    "lines": f.lines_of_code,
                    "rating": f.rating,
                    "suggestion": f.suggestion,
                }
                for f in self.complex_functions(10)
            ],
            "files": [
                {
                    "filepath": fc.filepath,
                    "total_lines": fc.total_lines,
                    "code_lines": fc.code_lines,
                    "functions": len(fc.functions),
                    "avg_cyclomatic": round(fc.avg_cyclomatic, 2),
                    "max_cyclomatic": fc.max_cyclomatic,
                    "rating": fc.rating,
                }
                for fc in self.files
            ],
        }


# ---------------------------------------------------------------------------
# Complexity computation
# ---------------------------------------------------------------------------

# Lua keywords that increase cyclomatic complexity
_BRANCH_KEYWORDS = re.compile(r"\b(if|elseif|while|for|repeat|and|or)\b")

# Function definition
_FUNC_DEF_RE = re.compile(
    r"^\s*(?:local\s+)?function\s+([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*(?::[A-Za-z_]\w*)?)\s*\(",
    re.MULTILINE,
)

# Nesting keywords
_NESTING_OPEN = re.compile(r"\b(if|while|for|repeat|function)\b")
_NESTING_CLOSE_END = re.compile(r"\bend\b")
_NESTING_CLOSE_UNTIL = re.compile(r"\buntil\b")


def _is_in_string_or_comment(line: str, pos: int) -> bool:
    """Check if position in line is inside a string or comment."""
    in_str = None
    i = 0
    while i < pos and i < len(line):
        ch = line[i]
        if in_str:
            if ch == in_str and (i == 0 or line[i - 1] != "\\"):
                in_str = None
        elif ch in ('"', "'"):
            in_str = ch
        elif ch == "-" and i + 1 < len(line) and line[i + 1] == "-":
            return True  # rest of line is comment
        i += 1
    return in_str is not None


def _count_branches(line: str) -> int:
    """Count branch keywords in a line of code, skipping strings/comments."""
    count = 0
    for m in _BRANCH_KEYWORDS.finditer(line):
        if not _is_in_string_or_comment(line, m.start()):
            count += 1
    return count


def _compute_nesting_depth(lines: List[str]) -> int:
    """Compute maximum nesting depth for a sequence of lines."""
    depth = 0
    max_depth = 0

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("--"):
            continue

        # Count opens and closes (very rough but effective for Lua)
        for m in _NESTING_OPEN.finditer(stripped):
            if not _is_in_string_or_comment(stripped, m.start()):
                depth += 1
                max_depth = max(max_depth, depth)

        for m in _NESTING_CLOSE_END.finditer(stripped):
            if not _is_in_string_or_comment(stripped, m.start()):
                depth = max(0, depth - 1)

        for m in _NESTING_CLOSE_UNTIL.finditer(stripped):
            if not _is_in_string_or_comment(stripped, m.start()):
                depth = max(0, depth - 1)

    return max_depth


def _find_function_end(lines: List[str], start_idx: int) -> int:
    """Find the end line index of a function starting at start_idx."""
    depth = 0
    for i in range(start_idx, len(lines)):
        stripped = lines[i].strip()
        if stripped.startswith("--"):
            continue

        # Count block openers
        for m in re.finditer(r"\b(function|if|while|for|repeat|do)\b", stripped):
            if not _is_in_string_or_comment(stripped, m.start()):
                kw = m.group(1)
                # 'do' after 'for ... do' is already counted by 'for'
                if kw == "do":
                    # Only count standalone 'do' blocks (rare)
                    before = stripped[: m.start()].strip()
                    if not re.search(r"\b(for|while)\b", before):
                        depth += 1
                else:
                    depth += 1

        for m in re.finditer(r"\bend\b", stripped):
            if not _is_in_string_or_comment(stripped, m.start()):
                depth -= 1
                if depth <= 0:
                    return i

        for m in _NESTING_CLOSE_UNTIL.finditer(stripped):
            if not _is_in_string_or_comment(stripped, m.start()):
                depth -= 1
                if depth <= 0:
                    return i

    return len(lines) - 1


def _generate_suggestion(func: FunctionComplexity) -> str:
    """Generate a refactoring suggestion based on complexity metrics."""
    parts = []
    if func.cyclomatic > 20:
        parts.append("Very high complexity - split into smaller functions")
    elif func.cyclomatic > 10:
        parts.append("Consider splitting into smaller functions")

    if func.max_nesting > 4:
        parts.append("Deep nesting - use early returns or guard clauses")

    if func.lines_of_code > 60:
        parts.append("Long function - extract helper functions")

    return "; ".join(parts) if parts else ""


def analyze_file_complexity(filepath: str, code: str) -> FileComplexity:
    """Analyze complexity for a single file."""
    lines = code.split("\n")
    fc = FileComplexity(filepath=filepath, total_lines=len(lines))

    # Count code lines (non-blank, non-comment)
    fc.code_lines = sum(
        1 for ln in lines if ln.strip() and not ln.strip().startswith("--")
    )

    # Find all function definitions
    for m in _FUNC_DEF_RE.finditer(code):
        func_name = m.group(1)
        start_line = code[: m.start()].count("\n")  # 0-based index
        end_line = _find_function_end(lines, start_line)

        func_lines = lines[start_line : end_line + 1]
        code_line_count = sum(
            1 for ln in func_lines if ln.strip() and not ln.strip().startswith("--")
        )

        # Cyclomatic: 1 base + count of branches
        cyclomatic = 1
        for ln in func_lines:
            stripped = ln.strip()
            if stripped.startswith("--"):
                continue
            cyclomatic += _count_branches(stripped)

        max_nesting = _compute_nesting_depth(func_lines)

        func_complexity = FunctionComplexity(
            name=func_name,
            filepath=filepath,
            start_line=start_line + 1,  # 1-based
            end_line=end_line + 1,
            lines_of_code=code_line_count,
            cyclomatic=cyclomatic,
            max_nesting=max_nesting,
        )
        func_complexity.suggestion = _generate_suggestion(func_complexity)
        fc.functions.append(func_complexity)

    return fc


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------


def analyze_complexity(directory: str) -> ComplexityReport:
    """Analyze complexity for all Lua files in a directory."""
    report = ComplexityReport()

    lua_files = find_lua_files(directory)
    report.total_scripts_scanned = len(lua_files)

    for filepath in lua_files:
        code = read_file_safe(filepath)
        if code is None:
            continue

        fc = analyze_file_complexity(filepath, code)
        report.files.append(fc)
        report.total_functions += len(fc.functions)

    return report
