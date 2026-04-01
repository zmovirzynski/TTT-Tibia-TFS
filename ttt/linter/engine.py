"""
Lint engine — Orchestrates rule execution on Lua files.

Handles:
  - Loading and filtering rules
  - Scanning directories for Lua files
  - Running rules on each file
  - Computing quality scores
  - Loading configuration from .tttlint.json
"""

import json
import os
import logging
from typing import Dict, List, Optional
from dataclasses import dataclass, field

from .rules import (
    LintRule, LintIssue, LintSeverity,
    get_all_rules, get_rules_by_ids,
)
from ..utils import read_file_safe, find_lua_files

logger = logging.getLogger("ttt")


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class FileLintResult:
    """Lint results for a single file."""
    filepath: str
    issues: List[LintIssue] = field(default_factory=list)
    score: int = 100
    error: str = ""

    @property
    def error_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == LintSeverity.ERROR)

    @property
    def warning_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == LintSeverity.WARNING)

    @property
    def info_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == LintSeverity.INFO)

    @property
    def hint_count(self) -> int:
        return sum(1 for i in self.issues if i.severity == LintSeverity.HINT)

    @property
    def fixable_count(self) -> int:
        return sum(1 for i in self.issues if i.fixable)


@dataclass
class LintReport:
    """Aggregated lint report for all files."""
    files: List[FileLintResult] = field(default_factory=list)
    rules_used: List[str] = field(default_factory=list)
    target_path: str = ""

    @property
    def total_issues(self) -> int:
        return sum(len(f.issues) for f in self.files)

    @property
    def total_errors(self) -> int:
        return sum(f.error_count for f in self.files)

    @property
    def total_warnings(self) -> int:
        return sum(f.warning_count for f in self.files)

    @property
    def total_infos(self) -> int:
        return sum(f.info_count for f in self.files)

    @property
    def total_fixable(self) -> int:
        return sum(f.fixable_count for f in self.files)

    @property
    def files_with_issues(self) -> int:
        return sum(1 for f in self.files if f.issues)

    @property
    def average_score(self) -> float:
        if not self.files:
            return 100.0
        return sum(f.score for f in self.files) / len(self.files)

    @property
    def overall_grade(self) -> str:
        avg = self.average_score
        if avg >= 90:
            return "A"
        elif avg >= 80:
            return "B"
        elif avg >= 70:
            return "C"
        elif avg >= 60:
            return "D"
        else:
            return "F"


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class LintConfig:
    """Configuration loaded from .tttlint.json."""
    enabled_rules: Optional[List[str]] = None    # None = all rules
    disabled_rules: List[str] = field(default_factory=list)
    severity_overrides: Dict[str, str] = field(default_factory=dict)
    ignore_patterns: List[str] = field(default_factory=list)
    max_issues_per_file: int = 50

    @classmethod
    def load(cls, config_path: str) -> "LintConfig":
        """Load config from a JSON file."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.debug(f"Could not load config {config_path}: {e}")
            return cls()

        return cls(
            enabled_rules=data.get("rules", None),
            disabled_rules=data.get("disable", []),
            severity_overrides=data.get("severity", {}),
            ignore_patterns=data.get("ignore", []),
            max_issues_per_file=data.get("maxIssuesPerFile", 50),
        )

    @classmethod
    def find_config(cls, start_dir: str) -> Optional[str]:
        """Walk up directories looking for .tttlint.json."""
        current = os.path.abspath(start_dir)
        while True:
            candidate = os.path.join(current, ".tttlint.json")
            if os.path.isfile(candidate):
                return candidate
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        return None


# ---------------------------------------------------------------------------
# Quality score calculator
# ---------------------------------------------------------------------------

def compute_score(issues: List[LintIssue], total_lines: int) -> int:
    """Compute a quality score from 0 to 100."""
    if total_lines == 0:
        return 100

    penalty = 0.0
    for issue in issues:
        if issue.severity == LintSeverity.ERROR:
            penalty += 15.0
        elif issue.severity == LintSeverity.WARNING:
            penalty += 5.0
        elif issue.severity == LintSeverity.INFO:
            penalty += 1.5
        elif issue.severity == LintSeverity.HINT:
            penalty += 0.5

    # Scale penalty relative to file size (bigger files get some slack)
    scale_factor = max(1.0, total_lines / 50.0)
    adjusted_penalty = penalty / scale_factor

    score = max(0, int(100 - adjusted_penalty))
    return score


# ---------------------------------------------------------------------------
# Lint Engine
# ---------------------------------------------------------------------------

class LintEngine:
    """Main lint engine that orchestrates rule execution."""

    def __init__(self, config: Optional[LintConfig] = None):
        self.config = config or LintConfig()
        self._rules: List[LintRule] = []
        self._load_rules()

    def _load_rules(self):
        """Load and filter rules based on configuration."""
        if self.config.enabled_rules is not None:
            self._rules = get_rules_by_ids(self.config.enabled_rules)
        else:
            self._rules = get_all_rules()

        # Remove disabled rules
        if self.config.disabled_rules:
            disabled = set(self.config.disabled_rules)
            self._rules = [r for r in self._rules if r.rule_id not in disabled]

        # Apply severity overrides
        for rule in self._rules:
            if rule.rule_id in self.config.severity_overrides:
                sev_str = self.config.severity_overrides[rule.rule_id].upper()
                try:
                    rule.severity = LintSeverity(sev_str)
                except ValueError:
                    logger.warning(f"Invalid severity '{sev_str}' for rule '{rule.rule_id}'")

        logger.debug(f"Loaded {len(self._rules)} lint rules: "
                     f"{[r.rule_id for r in self._rules]}")

    @property
    def rule_ids(self) -> List[str]:
        return [r.rule_id for r in self._rules]

    def lint_code(self, code: str, filename: str = "") -> FileLintResult:
        """Lint a string of Lua code."""
        result = FileLintResult(filepath=filename)
        lines = code.split("\n")

        for rule in self._rules:
            try:
                issues = rule.check(code, lines, filename)
                result.issues.extend(issues)
            except Exception as e:
                logger.warning(f"Rule '{rule.rule_id}' failed on {filename}: {e}")
                result.issues.append(LintIssue(
                    line=0, column=0,
                    severity=LintSeverity.ERROR,
                    rule_id=rule.rule_id,
                    message=f"Rule execution error: {e}",
                ))

        # Sort issues by line number
        result.issues.sort(key=lambda i: (i.line, i.column))

        # Limit issues per file
        if len(result.issues) > self.config.max_issues_per_file:
            truncated = len(result.issues) - self.config.max_issues_per_file
            result.issues = result.issues[:self.config.max_issues_per_file]
            result.issues.append(LintIssue(
                line=0, column=0,
                severity=LintSeverity.INFO,
                rule_id="lint-engine",
                message=f"... and {truncated} more issues (truncated)",
            ))

        # Compute quality score
        result.score = compute_score(result.issues, len(lines))

        return result

    def lint_file(self, filepath: str) -> FileLintResult:
        """Lint a single Lua file."""
        code = read_file_safe(filepath)
        if code is None:
            return FileLintResult(
                filepath=filepath,
                error=f"Could not read file: {filepath}",
                score=0,
            )

        result = self.lint_code(code, os.path.basename(filepath))
        result.filepath = filepath
        return result

    def lint_directory(self, directory: str) -> LintReport:
        """Lint all Lua files in a directory."""
        report = LintReport(
            rules_used=self.rule_ids,
            target_path=os.path.abspath(directory),
        )

        lua_files = find_lua_files(directory)
        if not lua_files:
            logger.info(f"No Lua files found in {directory}")
            return report

        logger.info(f"Linting {len(lua_files)} files in {directory}...")

        for filepath in lua_files:
            # Check ignore patterns
            rel_path = os.path.relpath(filepath, directory)
            if self._should_ignore(rel_path):
                logger.debug(f"  Skipping (ignored): {rel_path}")
                continue

            result = self.lint_file(filepath)
            report.files.append(result)

            if result.issues:
                logger.debug(f"  {rel_path}: {len(result.issues)} issues (score: {result.score})")
            else:
                logger.debug(f"  {rel_path}: clean ✓")

        return report

    def _should_ignore(self, rel_path: str) -> bool:
        """Check if file matches any ignore pattern."""
        import fnmatch
        for pattern in self.config.ignore_patterns:
            if fnmatch.fnmatch(rel_path, pattern):
                return True
        return False
