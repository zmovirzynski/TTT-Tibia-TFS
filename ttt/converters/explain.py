"""Explain collector — Tracks transformation reasoning for ``ttt convert --explain``."""

from dataclasses import dataclass, field
from typing import Dict, List
import json
import os


@dataclass
class ExplainEntry:
    """A single transformation explanation."""
    file: str = ""
    line: int = 0
    stage: str = ""          # signature, variable, function, constant, position
    original: str = ""
    transformed: str = ""
    rule: str = ""           # mapping key or rule name
    reasoning: str = ""
    confidence: float = 1.0


@dataclass
class ExplainReport:
    """Aggregated explain data for a full conversion run."""
    entries: List[ExplainEntry] = field(default_factory=list)

    def add(self, entry: ExplainEntry) -> None:
        self.entries.append(entry)

    @property
    def by_file(self) -> Dict[str, List[ExplainEntry]]:
        result: Dict[str, List[ExplainEntry]] = {}
        for e in self.entries:
            result.setdefault(e.file, []).append(e)
        return result

    @property
    def by_stage(self) -> Dict[str, int]:
        counts: Dict[str, int] = {}
        for e in self.entries:
            counts[e.stage] = counts.get(e.stage, 0) + 1
        return counts

    def to_dict(self) -> Dict:
        return {
            "total_transformations": len(self.entries),
            "by_stage": self.by_stage,
            "entries": [
                {
                    "file": e.file,
                    "line": e.line,
                    "stage": e.stage,
                    "original": e.original,
                    "transformed": e.transformed,
                    "rule": e.rule,
                    "reasoning": e.reasoning,
                    "confidence": e.confidence,
                }
                for e in self.entries
            ],
        }

    def to_text(self) -> str:
        lines = []
        lines.append("=" * 70)
        lines.append("  TTT Conversion Explain Report")
        lines.append("=" * 70)
        lines.append(f"  Total transformations: {len(self.entries)}")
        for stage, count in sorted(self.by_stage.items()):
            lines.append(f"    {stage}: {count}")
        lines.append("")

        for filename, entries in sorted(self.by_file.items()):
            lines.append(f"--- {filename} ({len(entries)} transformations) ---")
            for e in entries:
                conf_pct = f"{e.confidence * 100:.0f}%"
                lines.append(f"  L{e.line} [{e.stage}] ({conf_pct})")
                lines.append(f"    Rule: {e.rule}")
                lines.append(f"    {e.original}")
                lines.append(f"    → {e.transformed}")
                lines.append(f"    Reason: {e.reasoning}")
                lines.append("")
        return "\n".join(lines)

    def write(self, output_dir: str) -> str:
        """Write explain report files. Returns path to the text report."""
        os.makedirs(output_dir, exist_ok=True)

        text_path = os.path.join(output_dir, "conversion_explain.txt")
        with open(text_path, "w", encoding="utf-8") as f:
            f.write(self.to_text())

        json_path = os.path.join(output_dir, "conversion_explain.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)

        return text_path
