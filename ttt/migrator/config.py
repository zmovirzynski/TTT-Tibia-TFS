"""
Migration configuration model.

Defines which steps to run, input/output locations, and execution options.
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


# All available pipeline steps in execution order
DEFAULT_STEPS = ["convert", "fix", "analyze", "doctor", "docs"]


@dataclass
class MigrationConfig:
    """Configuration for a full server migration run."""

    # Required paths
    input_dir: str = ""
    output_dir: str = ""

    # Version settings (for the convert step)
    source_version: str = ""
    target_version: str = ""

    # Step selection (None = all steps)
    enabled_steps: Optional[List[str]] = None
    skip_steps: Optional[List[str]] = None

    # Execution modes
    dry_run: bool = False
    verbose: bool = False
    html_diff: bool = False

    # Backup
    backup: bool = True

    # Per-step overrides (step_name → dict of options)
    step_options: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    @property
    def steps(self) -> List[str]:
        """Return the ordered list of steps to execute."""
        if self.enabled_steps:
            return [s for s in DEFAULT_STEPS if s in self.enabled_steps]
        steps = list(DEFAULT_STEPS)
        if self.skip_steps:
            steps = [s for s in steps if s not in self.skip_steps]
        return steps

    @property
    def backup_dir(self) -> str:
        """Path for the pre-run backup snapshot."""
        if self.output_dir:
            return self.output_dir + "_backup"
        return ""

    @property
    def scripts_dir(self) -> str:
        """The converted scripts sub-directory inside output_dir."""
        if self.output_dir:
            return os.path.join(self.output_dir, "scripts")
        return ""

    @property
    def reports_dir(self) -> str:
        """The reports sub-directory inside output_dir."""
        if self.output_dir:
            return os.path.join(self.output_dir, "reports")
        return ""

    @property
    def docs_dir(self) -> str:
        """The docs sub-directory inside output_dir."""
        if self.output_dir:
            return os.path.join(self.output_dir, "docs")
        return ""

    def validate(self) -> List[str]:
        """Return a list of validation errors (empty = valid)."""
        errors = []

        if not self.input_dir:
            errors.append("input_dir is required")
        if not self.output_dir and not self.dry_run:
            errors.append("output_dir is required unless dry_run is enabled")

        # convert step needs version info
        if "convert" in self.steps:
            if not self.source_version:
                errors.append("source_version is required for the convert step")
            if not self.target_version:
                errors.append("target_version is required for the convert step")

        if self.enabled_steps:
            invalid = [s for s in self.enabled_steps if s not in DEFAULT_STEPS]
            if invalid:
                errors.append(f"Unknown steps: {', '.join(invalid)}")

        if self.skip_steps:
            invalid = [s for s in self.skip_steps if s not in DEFAULT_STEPS]
            if invalid:
                errors.append(f"Unknown steps to skip: {', '.join(invalid)}")

        return errors
