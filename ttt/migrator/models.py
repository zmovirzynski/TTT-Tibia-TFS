"""
Migration data models — StepResult, MigrationRunReport, StepStatus.
"""

import enum
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


# Canonical pipeline step names (in execution order)
PIPELINE_STEPS = ["convert", "fix", "analyze", "doctor", "docs"]

STEP_DESCRIPTIONS = {
    "convert": "Convert scripts between TFS versions",
    "fix": "Auto-fix common issues in converted scripts",
    "analyze": "Run server analysis (stats, dead code, complexity)",
    "doctor": "Health check (broken refs, conflicts, syntax)",
    "docs": "Generate server documentation",
}


class StepStatus(enum.Enum):
    """Status of a single pipeline step."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing one pipeline step."""

    name: str
    status: StepStatus = StepStatus.PENDING
    duration_seconds: float = 0.0
    error: str = ""
    outputs: Dict[str, Any] = field(default_factory=dict)
    summary: str = ""

    @property
    def ok(self) -> bool:
        return self.status == StepStatus.SUCCESS


@dataclass
class FileEntry:
    """Per-file data for the dashboard file table."""

    path: str = ""
    file_type: str = ""
    changes: int = 0
    ttt_markers: int = 0
    confidence: str = "HIGH"
    has_diff: bool = False


@dataclass
class MigrationRunReport:
    """Full report for a migration run across all steps."""

    input_dir: str = ""
    output_dir: str = ""
    source_version: str = ""
    target_version: str = ""
    dry_run: bool = False
    backup_dir: str = ""
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    steps: List[StepResult] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)
    file_entries: List[FileEntry] = field(default_factory=list)

    @property
    def total_duration_seconds(self) -> float:
        if self.started_at and self.finished_at:
            return (self.finished_at - self.started_at).total_seconds()
        return sum(s.duration_seconds for s in self.steps)

    @property
    def steps_succeeded(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.SUCCESS)

    @property
    def steps_failed(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.FAILED)

    @property
    def steps_skipped(self) -> int:
        return sum(1 for s in self.steps if s.status == StepStatus.SKIPPED)

    @property
    def success(self) -> bool:
        return self.steps_failed == 0

    # ------------------------------------------------------------------
    # Executive summary helpers
    # ------------------------------------------------------------------

    @property
    def files_converted(self) -> int:
        s = self.get_step("convert")
        if s and s.ok:
            stats = s.outputs.get("stats", {})
            return stats.get("lua_files_processed", 0) + stats.get(
                "xml_files_processed", 0
            )
        return 0

    @property
    def ttt_markers(self) -> int:
        s = self.get_step("convert")
        if s and s.ok:
            stats = s.outputs.get("stats", {})
            return stats.get("warnings", 0)
        return 0

    @property
    def doctor_issues(self) -> int:
        s = self.get_step("doctor")
        if s and s.ok:
            return s.outputs.get("total_issues", 0)
        return 0

    @property
    def health_score(self) -> Optional[int]:
        s = self.get_step("doctor")
        if s and s.ok:
            return s.outputs.get("health_score")
        return None

    @property
    def health_rating(self) -> str:
        s = self.get_step("doctor")
        if s and s.ok:
            return s.outputs.get("health_rating", "N/A")
        return "N/A"

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_step(self, name: str) -> Optional[StepResult]:
        for s in self.steps:
            if s.name == name:
                return s
        return None

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to a plain dict for JSON export."""
        return {
            "input_dir": self.input_dir,
            "output_dir": self.output_dir,
            "source_version": self.source_version,
            "target_version": self.target_version,
            "dry_run": self.dry_run,
            "backup_dir": self.backup_dir,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "total_duration_seconds": round(self.total_duration_seconds, 2),
            "steps_succeeded": self.steps_succeeded,
            "steps_failed": self.steps_failed,
            "steps_skipped": self.steps_skipped,
            "success": self.success,
            "files_converted": self.files_converted,
            "ttt_markers": self.ttt_markers,
            "doctor_issues": self.doctor_issues,
            "health_score": self.health_score,
            "health_rating": self.health_rating,
            "artifacts": dict(self.artifacts),
            "file_entries": [
                {
                    "path": f.path,
                    "file_type": f.file_type,
                    "changes": f.changes,
                    "ttt_markers": f.ttt_markers,
                    "confidence": f.confidence,
                    "has_diff": f.has_diff,
                }
                for f in self.file_entries
            ],
            "steps": [
                {
                    "name": s.name,
                    "status": s.status.value,
                    "duration_seconds": round(s.duration_seconds, 2),
                    "error": s.error,
                    "summary": s.summary,
                    "outputs": {k: str(v) for k, v in s.outputs.items()},
                }
                for s in self.steps
            ],
        }
