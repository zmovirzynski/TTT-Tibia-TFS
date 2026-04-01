"""
Example Custom Rule Pack for TTT

This file demonstrates how to extend TTT with custom lint rules.
Place it in your project and reference it from ttt.project.toml:

    [plugins]
    rules = ["./custom/my_rules.py"]

Each rule must subclass LintRule and be registered in the RULES dict.
"""

import re
from typing import List

from ttt.linter.rules import LintRule, LintIssue, LintSeverity


class PrintCallRule(LintRule):
    """Detects bare print() calls which are often left-over debug statements."""

    rule_id = "custom-no-print"
    description = "Detects bare print() calls (likely debug leftovers)"
    severity = LintSeverity.WARNING

    _pattern = re.compile(r"\bprint\s*\(")

    def check(self, code: str, lines: List[str], filename: str = "") -> List[LintIssue]:
        issues = []
        for i, line in enumerate(lines, 1):
            stripped = line.lstrip()
            if stripped.startswith("--"):
                continue
            for match in self._pattern.finditer(line):
                issues.append(
                    LintIssue(
                        line=i,
                        column=match.start() + 1,
                        severity=self.severity,
                        rule_id=self.rule_id,
                        message="Bare print() call detected — likely a debug leftover",
                        suggestion="Remove or replace with a proper logging call",
                    )
                )
        return issues


# ── Registry ──────────────────────────────────────────────────────────────
# The RULES dict is required. Keys must match each class's rule_id.

RULES = {
    "custom-no-print": PrintCallRule,
}
