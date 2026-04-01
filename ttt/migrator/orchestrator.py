"""
Migration orchestrator — Runs the multi-step migration pipeline.

Steps (in order): convert → fix → analyze → doctor → docs
Each step is independently failable; one failure does not corrupt the run.
"""

import json
import logging
import os
import shutil
import time
from datetime import datetime

from .config import MigrationConfig
from .models import (
    MigrationRunReport,
    StepResult,
    StepStatus,
    STEP_DESCRIPTIONS,
)

logger = logging.getLogger("ttt")


class MigrationOrchestrator:
    """Executes a full migration pipeline based on a MigrationConfig."""

    def __init__(self, config: MigrationConfig):
        self.config = config
        self.report = MigrationRunReport(
            input_dir=config.input_dir,
            output_dir=config.output_dir,
            source_version=config.source_version,
            target_version=config.target_version,
            dry_run=config.dry_run,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self) -> MigrationRunReport:
        """Execute the full pipeline and return the run report."""
        errors = self.config.validate()
        if errors:
            for e in errors:
                logger.error(f"Config error: {e}")
            return self.report

        self.report.started_at = datetime.now()
        logger.info("=" * 60)
        logger.info("  TTT — Server Migration")
        logger.info("=" * 60)
        logger.info(f"  Input:   {self.config.input_dir}")
        logger.info(f"  Output:  {self.config.output_dir or '(dry-run)'}")
        logger.info(f"  From:    {self.config.source_version}")
        logger.info(f"  To:      {self.config.target_version}")
        logger.info(f"  Steps:   {', '.join(self.config.steps)}")
        if self.config.dry_run:
            logger.info("  Mode:    DRY RUN")
        logger.info("=" * 60)
        logger.info("")

        # Pre-run backup
        if not self.config.dry_run and self.config.backup:
            self._create_backup()

        # Create output workspace layout
        if not self.config.dry_run and self.config.output_dir:
            self._create_workspace_layout()

        for step_name in self.config.steps:
            self._run_step(step_name)

        # Count TTT markers in converted output
        if not self.config.dry_run and self.config.output_dir:
            self.report.artifacts["output_dir"] = self.config.output_dir
            self._count_ttt_markers()
            self._generate_review_report()

        # Write reports
        if not self.config.dry_run and self.config.output_dir:
            self._write_reports()

        self.report.finished_at = datetime.now()
        return self.report

    # ------------------------------------------------------------------
    # Pre-run backup
    # ------------------------------------------------------------------

    def _create_backup(self) -> None:
        """Create a backup snapshot of the input directory."""
        backup_dir = self.config.backup_dir
        if not backup_dir:
            return

        if os.path.exists(backup_dir):
            logger.info(f"  Backup already exists: {backup_dir} (skipping)")
            self.report.backup_dir = backup_dir
            return

        logger.info(f"  Creating backup: {backup_dir}")
        try:
            shutil.copytree(self.config.input_dir, backup_dir)
            self.report.backup_dir = backup_dir
            self.report.artifacts["backup_dir"] = backup_dir
            logger.info(f"  Backup created: {backup_dir}")
        except Exception as exc:
            logger.warning(f"  Backup failed: {exc}")

    # ------------------------------------------------------------------
    # Output workspace layout
    # ------------------------------------------------------------------

    def _create_workspace_layout(self) -> None:
        """Create the output workspace directory structure."""
        os.makedirs(self.config.output_dir, exist_ok=True)
        os.makedirs(self.config.reports_dir, exist_ok=True)
        logger.info(f"  Output workspace: {self.config.output_dir}")
        logger.info("")

    # ------------------------------------------------------------------
    # Step dispatch
    # ------------------------------------------------------------------

    def _run_step(self, name: str) -> StepResult:
        """Run a single pipeline step, catching errors gracefully."""
        desc = STEP_DESCRIPTIONS.get(name, name)
        logger.info(f"[{name}] {desc}")

        result = StepResult(name=name, status=StepStatus.RUNNING)
        self.report.steps.append(result)

        runner = {
            "convert": self._step_convert,
            "fix": self._step_fix,
            "analyze": self._step_analyze,
            "doctor": self._step_doctor,
            "docs": self._step_docs,
        }.get(name)

        if runner is None:
            result.status = StepStatus.SKIPPED
            result.summary = f"Unknown step: {name}"
            logger.warning(f"  Skipping unknown step: {name}")
            return result

        t0 = time.time()
        try:
            runner(result)
            if result.status == StepStatus.RUNNING:
                result.status = StepStatus.SUCCESS
        except Exception as exc:
            result.status = StepStatus.FAILED
            result.error = str(exc)
            logger.error(f"  Step '{name}' failed: {exc}")
        finally:
            result.duration_seconds = time.time() - t0
            label = result.status.value.upper()
            logger.info(f"  [{label}] {name} ({result.duration_seconds:.1f}s)")
            logger.info("")

        return result

    # ------------------------------------------------------------------
    # Individual step implementations
    # ------------------------------------------------------------------

    def _step_convert(self, result: StepResult) -> None:
        from ..engine import ConversionEngine

        output_dir = self.config.output_dir
        if self.config.dry_run:
            output_dir = ""

        engine = ConversionEngine(
            source_version=self.config.source_version,
            target_version=self.config.target_version,
            input_dir=self.config.input_dir,
            output_dir=output_dir,
            verbose=self.config.verbose,
            dry_run=self.config.dry_run,
            html_diff=self.config.html_diff,
        )

        validation_errors = engine.validate()
        if validation_errors:
            result.status = StepStatus.FAILED
            result.error = "; ".join(validation_errors)
            return

        stats = engine.run()
        result.outputs["stats"] = stats
        result.summary = (
            f"Converted {stats.get('lua_files_processed', 0)} Lua files, "
            f"{stats.get('xml_files_processed', 0)} XML files, "
            f"{stats.get('errors', 0)} errors"
        )

        # Extract per-file data for the dashboard file table
        from .models import FileEntry

        has_diff = self.config.html_diff
        if hasattr(engine, "report") and engine.report:
            for fr in engine.report.file_reports:
                rel = os.path.relpath(fr.source_path, self.config.input_dir) if self.config.input_dir else os.path.basename(fr.source_path)
                self.report.file_entries.append(FileEntry(
                    path=rel,
                    file_type=fr.file_type or fr.conversion_type or "",
                    changes=fr.total_changes,
                    ttt_markers=fr.ttt_warnings,
                    confidence=fr.confidence_label,
                    has_diff=has_diff,
                ))

        # Track conversion report artifact
        if not self.config.dry_run and self.config.output_dir:
            report_path = os.path.join(self.config.output_dir, "conversion_report.txt")
            if os.path.exists(report_path):
                self.report.artifacts["conversion_report"] = report_path

        if stats.get("errors", 0) > 0:
            result.status = StepStatus.FAILED
            result.error = f"{stats['errors']} conversion error(s)"

    def _step_fix(self, result: StepResult) -> None:
        from ..fixer.auto_fix import FixEngine

        target_dir = self.config.output_dir or self.config.input_dir

        engine = FixEngine(
            dry_run=self.config.dry_run,
            create_backup=False,
        )

        report = engine.fix_directory(target_dir)
        result.outputs["total_fixes"] = report.total_fixes
        result.outputs["files_changed"] = report.files_changed
        result.summary = (
            f"{report.total_fixes} fixes applied across {report.files_changed} files"
        )

    def _step_analyze(self, result: StepResult) -> None:
        from ..analyzer.engine import AnalyzeEngine

        target_dir = self.config.output_dir or self.config.input_dir

        engine = AnalyzeEngine()
        report = engine.analyze(target_dir)

        result.outputs["total_issues"] = report.total_issues
        if report.stats:
            result.outputs["total_lua_files"] = report.stats.total_lua_files
            result.outputs["total_lines"] = report.stats.total_lines
        result.summary = f"{report.total_issues} issues found"

    def _step_doctor(self, result: StepResult) -> None:
        from ..doctor.engine import DoctorEngine

        target_dir = self.config.output_dir or self.config.input_dir

        engine = DoctorEngine()
        report = engine.diagnose(target_dir)

        result.outputs["health_score"] = report.health_score
        result.outputs["health_rating"] = report.health_rating
        result.outputs["total_issues"] = report.total_issues
        result.summary = (
            f"Score: {report.health_score}/100 ({report.health_rating}), "
            f"{report.total_issues} issues"
        )

    def _step_docs(self, result: StepResult) -> None:
        from ..docs import DocsGenerator

        target_dir = self.config.output_dir or self.config.input_dir

        gen = DocsGenerator()
        report = gen.generate(target_dir)

        result.outputs["total_entries"] = report.total_entries

        if not self.config.dry_run and self.config.output_dir:
            from ..docs import export_markdown

            docs_dir = self.config.docs_dir
            written = export_markdown(report, docs_dir)
            result.outputs["docs_dir"] = docs_dir
            result.outputs["files_written"] = len(written)
            self.report.artifacts["docs_dir"] = docs_dir
            result.summary = (
                f"{report.total_entries} entries documented, "
                f"{len(written)} files written to {docs_dir}"
            )
        else:
            result.summary = (
                f"{report.total_entries} entries documented (dry-run, not written)"
            )

    # ------------------------------------------------------------------
    # Post-run: TTT marker counting
    # ------------------------------------------------------------------

    def _count_ttt_markers(self) -> None:
        """Walk output dir and count '-- TTT:' markers across all Lua files."""
        total = 0
        output = self.config.output_dir
        if not output or not os.path.isdir(output):
            return
        for root, _, files in os.walk(output):
            for fname in files:
                if fname.endswith(".lua"):
                    fpath = os.path.join(root, fname)
                    try:
                        with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                            total += sum(1 for line in f if "-- TTT:" in line)
                    except OSError:
                        pass
        # Store on convert step if present
        convert_step = self.report.get_step("convert")
        if convert_step:
            convert_step.outputs["ttt_markers"] = total

    def _generate_review_report(self) -> None:
        """Generate a review report for residual -- TTT: markers."""
        output = self.config.output_dir
        if not output or not os.path.isdir(output):
            return

        from ..review import ReviewScanner, format_review_html, format_review_json

        scanner = ReviewScanner()
        report = scanner.scan_with_relative_paths(output)
        if report.total_markers == 0:
            return

        reports_dir = self.config.reports_dir
        os.makedirs(reports_dir, exist_ok=True)

        # HTML review report
        html_path = os.path.join(reports_dir, "review_report.html")
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(format_review_html(report))
        self.report.artifacts["review_report_html"] = html_path
        logger.info(f"  Review report:     {html_path}")

        # JSON review report
        json_path = os.path.join(reports_dir, "review_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            f.write(format_review_json(report))
        self.report.artifacts["review_report_json"] = json_path

    # ------------------------------------------------------------------
    # Post-run: write reports
    # ------------------------------------------------------------------

    def _write_reports(self) -> None:
        """Write the migration summary as markdown and JSON to reports/."""
        reports_dir = self.config.reports_dir
        os.makedirs(reports_dir, exist_ok=True)

        # Markdown summary
        md_path = os.path.join(reports_dir, "migration_summary.md")
        md_content = format_migration_markdown(self.report)
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        self.report.artifacts["migration_summary_md"] = md_path
        logger.info(f"  Migration summary: {md_path}")

        # JSON report
        json_path = os.path.join(reports_dir, "migration_report.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(self.report.to_dict(), f, indent=2)
        self.report.artifacts["migration_report_json"] = json_path
        logger.info(f"  Migration report:  {json_path}")

        # HTML Dashboard
        try:
            from ..dashboard import generate_dashboard
            dash_path = os.path.join(reports_dir, "dashboard.html")
            generate_dashboard(self.report, dash_path)
            self.report.artifacts["dashboard_html"] = dash_path
            logger.info(f"  Dashboard:         {dash_path}")
        except Exception as exc:
            logger.warning(f"  Dashboard generation failed: {exc}")


# ---------------------------------------------------------------------------
# Terminal summary formatter
# ---------------------------------------------------------------------------

_SEP = "=" * 60
_THIN = "-" * 60


def format_migration_summary(report: MigrationRunReport) -> str:
    """Format a human-readable terminal summary of the migration run."""
    lines = []
    lines.append("")
    lines.append(_SEP)
    lines.append("  TTT — Migration Summary")
    lines.append(_SEP)
    lines.append(f"  Input:    {report.input_dir}")
    lines.append(f"  Output:   {report.output_dir or '(dry-run)'}")
    lines.append(f"  From:     {report.source_version}")
    lines.append(f"  To:       {report.target_version}")
    if report.dry_run:
        lines.append("  Mode:     DRY RUN")
    if report.backup_dir:
        lines.append(f"  Backup:   {report.backup_dir}")
    lines.append(f"  Duration: {report.total_duration_seconds:.1f}s")
    lines.append("")

    # Per-step table
    lines.append("  Steps:")
    lines.append(f"  {'Step':<12s} {'Status':<10s} {'Time':>6s}  Summary")
    lines.append(f"  {_THIN}")
    for step in report.steps:
        status_str = step.status.value.upper()
        time_str = f"{step.duration_seconds:.1f}s"
        summary = step.summary or step.error or ""
        lines.append(f"  {step.name:<12s} {status_str:<10s} {time_str:>6s}  {summary}")
    lines.append("")

    # Executive summary
    lines.append("  Executive Summary:")
    lines.append(f"  {_THIN}")
    if report.files_converted:
        lines.append(f"  Files converted:     {report.files_converted}")
    convert_step = report.get_step("convert")
    if convert_step and convert_step.ok:
        markers = convert_step.outputs.get("ttt_markers", 0)
        lines.append(f"  -- TTT: markers:     {markers}")
    if report.health_score is not None:
        lines.append(f"  Health score:        {report.health_score}/100 ({report.health_rating})")
    if report.doctor_issues:
        lines.append(f"  Doctor issues:       {report.doctor_issues}")
    fix_step = report.get_step("fix")
    if fix_step and fix_step.ok:
        lines.append(f"  Auto-fixes applied:  {fix_step.outputs.get('total_fixes', 0)}")
    lines.append("")

    # Artifacts
    if report.artifacts:
        lines.append("  Artifacts:")
        lines.append(f"  {_THIN}")
        for label, path in report.artifacts.items():
            lines.append(f"  {label:<25s} {path}")
        lines.append("")

    # Totals
    lines.append(
        f"  Result: {report.steps_succeeded} succeeded, "
        f"{report.steps_failed} failed, "
        f"{report.steps_skipped} skipped"
    )

    if report.success:
        lines.append("  Status: SUCCESS")
    else:
        lines.append("  Status: FAILED")

    lines.append(_SEP)
    lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Markdown summary exporter
# ---------------------------------------------------------------------------


def format_migration_markdown(report: MigrationRunReport) -> str:
    """Export the migration run report as a Markdown document."""
    lines = []
    lines.append("# TTT Migration Summary")
    lines.append("")
    lines.append("| Field | Value |")
    lines.append("|-------|-------|")
    lines.append(f"| Input | `{report.input_dir}` |")
    lines.append(f"| Output | `{report.output_dir or '(dry-run)'}` |")
    lines.append(f"| Source | {report.source_version} |")
    lines.append(f"| Target | {report.target_version} |")
    if report.dry_run:
        lines.append("| Mode | DRY RUN |")
    if report.backup_dir:
        lines.append(f"| Backup | `{report.backup_dir}` |")
    lines.append(f"| Duration | {report.total_duration_seconds:.1f}s |")
    lines.append(f"| Status | **{'SUCCESS' if report.success else 'FAILED'}** |")
    lines.append("")

    # Executive summary
    lines.append("## Executive Summary")
    lines.append("")
    if report.files_converted:
        lines.append(f"- **Files converted:** {report.files_converted}")
    convert_step = report.get_step("convert")
    if convert_step and convert_step.ok:
        markers = convert_step.outputs.get("ttt_markers", 0)
        lines.append(f"- **`-- TTT:` markers:** {markers}")
    if report.artifacts.get("review_report_html"):
        lines.append(f"- **Review report:** [`review_report.html`]({report.artifacts['review_report_html']})")
    if report.health_score is not None:
        lines.append(f"- **Health score:** {report.health_score}/100 ({report.health_rating})")
    if report.doctor_issues:
        lines.append(f"- **Doctor issues:** {report.doctor_issues}")
    fix_step = report.get_step("fix")
    if fix_step and fix_step.ok:
        lines.append(f"- **Auto-fixes applied:** {fix_step.outputs.get('total_fixes', 0)}")
    docs_step = report.get_step("docs")
    if docs_step and docs_step.ok:
        lines.append(f"- **Documentation entries:** {docs_step.outputs.get('total_entries', 0)}")
    lines.append("")

    # Step details
    lines.append("## Pipeline Steps")
    lines.append("")
    lines.append("| Step | Status | Duration | Summary |")
    lines.append("|------|--------|----------|---------|")
    for step in report.steps:
        status = step.status.value.upper()
        dur = f"{step.duration_seconds:.1f}s"
        summary = step.summary or step.error or ""
        lines.append(f"| {step.name} | {status} | {dur} | {summary} |")
    lines.append("")

    # Artifacts
    if report.artifacts:
        lines.append("## Artifacts")
        lines.append("")
        for label, path in report.artifacts.items():
            lines.append(f"- **{label}:** `{path}`")
        lines.append("")

    return "\n".join(lines)
