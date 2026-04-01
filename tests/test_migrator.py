"""
Tests for the migration orchestrator (Sprint 1 + Sprint 2).

Covers:
  - MigrationConfig validation, step selection, workspace paths
  - MigrationRunReport model (executive summary helpers)
  - MigrationOrchestrator execution (backup, workspace layout, reports)
  - Dry-run mode
  - Terminal summary + markdown export formatting
  - Integration test using examples/tfs03_input
"""

import os
import sys
import json
import shutil
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ttt.migrator.config import MigrationConfig, DEFAULT_STEPS
from ttt.migrator.models import (
    MigrationRunReport,
    StepResult,
    StepStatus,
)
from ttt.migrator.orchestrator import (
    MigrationOrchestrator,
    format_migration_summary,
    format_migration_markdown,
)


# ---------------------------------------------------------------------------
# MigrationConfig tests
# ---------------------------------------------------------------------------


class TestMigrationConfig(unittest.TestCase):
    """Tests for config validation and step selection."""

    def test_default_steps(self):
        cfg = MigrationConfig()
        self.assertEqual(cfg.steps, DEFAULT_STEPS)

    def test_enabled_steps_filter(self):
        cfg = MigrationConfig(enabled_steps=["convert", "fix"])
        self.assertEqual(cfg.steps, ["convert", "fix"])

    def test_enabled_steps_preserves_order(self):
        cfg = MigrationConfig(enabled_steps=["docs", "convert"])
        # Should respect the canonical order, not the user order
        self.assertEqual(cfg.steps, ["convert", "docs"])

    def test_skip_steps(self):
        cfg = MigrationConfig(skip_steps=["docs", "fix"])
        self.assertEqual(cfg.steps, ["convert", "analyze", "doctor"])

    def test_validate_missing_input(self):
        cfg = MigrationConfig(
            output_dir="/tmp/out",
            source_version="tfs03",
            target_version="revscript",
        )
        errors = cfg.validate()
        self.assertTrue(any("input_dir" in e for e in errors))

    def test_validate_missing_output_without_dry_run(self):
        cfg = MigrationConfig(
            input_dir="/tmp/in",
            source_version="tfs03",
            target_version="revscript",
        )
        errors = cfg.validate()
        self.assertTrue(any("output_dir" in e for e in errors))

    def test_validate_dry_run_no_output_ok(self):
        cfg = MigrationConfig(
            input_dir="/tmp/in",
            source_version="tfs03",
            target_version="revscript",
            dry_run=True,
        )
        errors = cfg.validate()
        # Should not complain about output_dir
        self.assertFalse(any("output_dir" in e for e in errors))

    def test_validate_missing_version_for_convert(self):
        cfg = MigrationConfig(
            input_dir="/tmp/in",
            output_dir="/tmp/out",
        )
        errors = cfg.validate()
        self.assertTrue(any("source_version" in e for e in errors))
        self.assertTrue(any("target_version" in e for e in errors))

    def test_validate_skip_convert_no_version_needed(self):
        cfg = MigrationConfig(
            input_dir="/tmp/in",
            output_dir="/tmp/out",
            enabled_steps=["analyze", "doctor"],
        )
        errors = cfg.validate()
        # No version errors since convert is not in the steps
        self.assertFalse(any("source_version" in e for e in errors))

    def test_validate_unknown_steps(self):
        cfg = MigrationConfig(
            input_dir="/tmp/in",
            output_dir="/tmp/out",
            enabled_steps=["convert", "magic"],
        )
        errors = cfg.validate()
        self.assertTrue(any("Unknown steps" in e for e in errors))

    def test_validate_unknown_skip_steps(self):
        cfg = MigrationConfig(
            input_dir="/tmp/in",
            output_dir="/tmp/out",
            enabled_steps=["convert"],
            source_version="tfs03",
            target_version="revscript",
            skip_steps=["magic"],
        )
        errors = cfg.validate()
        self.assertTrue(any("Unknown steps to skip" in e for e in errors))

    def test_workspace_path_properties(self):
        cfg = MigrationConfig(output_dir="/tmp/migrated")
        self.assertEqual(cfg.scripts_dir, os.path.join("/tmp/migrated", "scripts"))
        self.assertEqual(cfg.reports_dir, os.path.join("/tmp/migrated", "reports"))
        self.assertEqual(cfg.docs_dir, os.path.join("/tmp/migrated", "docs"))
        self.assertEqual(cfg.backup_dir, "/tmp/migrated_backup")

    def test_workspace_paths_empty_when_no_output(self):
        cfg = MigrationConfig(dry_run=True)
        self.assertEqual(cfg.scripts_dir, "")
        self.assertEqual(cfg.reports_dir, "")
        self.assertEqual(cfg.docs_dir, "")
        self.assertEqual(cfg.backup_dir, "")


# ---------------------------------------------------------------------------
# MigrationRunReport tests
# ---------------------------------------------------------------------------


class TestMigrationRunReport(unittest.TestCase):
    """Tests for the run report model."""

    def test_empty_report(self):
        r = MigrationRunReport()
        self.assertEqual(r.steps_succeeded, 0)
        self.assertEqual(r.steps_failed, 0)
        self.assertEqual(r.steps_skipped, 0)
        self.assertTrue(r.success)

    def test_report_with_steps(self):
        r = MigrationRunReport(
            steps=[
                StepResult(name="convert", status=StepStatus.SUCCESS, duration_seconds=1.0),
                StepResult(name="fix", status=StepStatus.SUCCESS, duration_seconds=0.5),
                StepResult(name="analyze", status=StepStatus.FAILED, error="boom"),
            ]
        )
        self.assertEqual(r.steps_succeeded, 2)
        self.assertEqual(r.steps_failed, 1)
        self.assertFalse(r.success)

    def test_get_step(self):
        s = StepResult(name="doctor", status=StepStatus.SUCCESS)
        r = MigrationRunReport(steps=[s])
        self.assertIs(r.get_step("doctor"), s)
        self.assertIsNone(r.get_step("nonexistent"))

    def test_to_dict_serializable(self):
        r = MigrationRunReport(
            input_dir="/in",
            output_dir="/out",
            source_version="tfs03",
            target_version="revscript",
            steps=[
                StepResult(name="convert", status=StepStatus.SUCCESS, duration_seconds=2.3),
            ],
        )
        d = r.to_dict()
        # Must be JSON-serializable
        serialized = json.dumps(d)
        self.assertIn("convert", serialized)
        self.assertIn("success", d["steps"][0]["status"])

    def test_step_result_ok(self):
        s = StepResult(name="x", status=StepStatus.SUCCESS)
        self.assertTrue(s.ok)
        s.status = StepStatus.FAILED
        self.assertFalse(s.ok)

    def test_executive_summary_helpers(self):
        r = MigrationRunReport(
            steps=[
                StepResult(
                    name="convert",
                    status=StepStatus.SUCCESS,
                    outputs={"stats": {"lua_files_processed": 5, "xml_files_processed": 3, "warnings": 2}},
                ),
                StepResult(
                    name="doctor",
                    status=StepStatus.SUCCESS,
                    outputs={"health_score": 85, "health_rating": "WARNING", "total_issues": 4},
                ),
            ]
        )
        self.assertEqual(r.files_converted, 8)
        self.assertEqual(r.ttt_markers, 2)
        self.assertEqual(r.doctor_issues, 4)
        self.assertEqual(r.health_score, 85)
        self.assertEqual(r.health_rating, "WARNING")

    def test_executive_summary_defaults_without_steps(self):
        r = MigrationRunReport()
        self.assertEqual(r.files_converted, 0)
        self.assertEqual(r.ttt_markers, 0)
        self.assertEqual(r.doctor_issues, 0)
        self.assertIsNone(r.health_score)
        self.assertEqual(r.health_rating, "N/A")

    def test_to_dict_includes_new_fields(self):
        r = MigrationRunReport(
            input_dir="/in",
            output_dir="/out",
            backup_dir="/out_backup",
            artifacts={"conversion_report": "/out/conversion_report.txt"},
        )
        d = r.to_dict()
        self.assertEqual(d["backup_dir"], "/out_backup")
        self.assertIn("conversion_report", d["artifacts"])
        self.assertIn("health_score", d)
        self.assertIn("files_converted", d)


# ---------------------------------------------------------------------------
# MigrationOrchestrator tests
# ---------------------------------------------------------------------------


class TestMigrationOrchestrator(unittest.TestCase):
    """Integration tests for the orchestrator."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="ttt_test_")
        self.input_dir = os.path.join(self.tmpdir, "input")
        os.makedirs(self.input_dir)
        self.output_dir = os.path.join(self.tmpdir, "output")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_dry_run_with_all_steps(self):
        cfg = MigrationConfig(
            input_dir=self.input_dir,
            source_version="tfs03",
            target_version="revscript",
            dry_run=True,
            enabled_steps=["convert", "analyze", "doctor"],
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()

        self.assertIsNotNone(report.started_at)
        self.assertIsNotNone(report.finished_at)
        self.assertEqual(len(report.steps), 3)
        for step in report.steps:
            self.assertNotEqual(step.status, StepStatus.PENDING)
            self.assertNotEqual(step.status, StepStatus.RUNNING)

    def test_config_validation_prevents_run(self):
        cfg = MigrationConfig()
        orch = MigrationOrchestrator(cfg)
        report = orch.run()
        self.assertEqual(len(report.steps), 0)

    def test_single_step_execution(self):
        cfg = MigrationConfig(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            enabled_steps=["analyze"],
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()

        self.assertEqual(len(report.steps), 1)
        self.assertEqual(report.steps[0].name, "analyze")

    def test_failed_step_does_not_block_next(self):
        lua_file = os.path.join(self.input_dir, "test.lua")
        with open(lua_file, "w") as f:
            f.write("-- empty script\n")

        cfg = MigrationConfig(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            source_version="tfs03",
            target_version="revscript",
            enabled_steps=["convert", "analyze", "doctor"],
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()
        self.assertEqual(len(report.steps), 3)

    def test_total_duration(self):
        cfg = MigrationConfig(
            input_dir=self.input_dir,
            dry_run=True,
            enabled_steps=["analyze"],
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()
        self.assertGreater(report.total_duration_seconds, 0)

    def test_skip_steps(self):
        cfg = MigrationConfig(
            input_dir=self.input_dir,
            dry_run=True,
            source_version="tfs03",
            target_version="revscript",
            skip_steps=["fix", "docs"],
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()

        step_names = [s.name for s in report.steps]
        self.assertNotIn("fix", step_names)
        self.assertNotIn("docs", step_names)
        self.assertIn("convert", step_names)

    def test_backup_created(self):
        """Backup should be created before migration when backup=True."""
        lua_file = os.path.join(self.input_dir, "test.lua")
        with open(lua_file, "w") as f:
            f.write("print('hello')\n")

        cfg = MigrationConfig(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            enabled_steps=["analyze"],
            backup=True,
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()

        self.assertTrue(os.path.isdir(cfg.backup_dir))
        self.assertTrue(os.path.isfile(os.path.join(cfg.backup_dir, "test.lua")))
        self.assertEqual(report.backup_dir, cfg.backup_dir)

    def test_no_backup_when_disabled(self):
        lua_file = os.path.join(self.input_dir, "test.lua")
        with open(lua_file, "w") as f:
            f.write("print('hello')\n")

        cfg = MigrationConfig(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            enabled_steps=["analyze"],
            backup=False,
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()

        self.assertFalse(os.path.exists(cfg.backup_dir))
        self.assertEqual(report.backup_dir, "")

    def test_no_backup_in_dry_run(self):
        cfg = MigrationConfig(
            input_dir=self.input_dir,
            dry_run=True,
            enabled_steps=["analyze"],
            backup=True,
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()
        # Dry-run should not create backup
        self.assertEqual(report.backup_dir, "")

    def test_workspace_layout_created(self):
        cfg = MigrationConfig(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            enabled_steps=["analyze"],
        )
        orch = MigrationOrchestrator(cfg)
        orch.run()

        self.assertTrue(os.path.isdir(self.output_dir))
        self.assertTrue(os.path.isdir(cfg.reports_dir))

    def test_reports_written(self):
        """Non-dry-run should write migration_summary.md and migration_report.json."""
        cfg = MigrationConfig(
            input_dir=self.input_dir,
            output_dir=self.output_dir,
            enabled_steps=["analyze", "doctor"],
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()

        md_path = os.path.join(cfg.reports_dir, "migration_summary.md")
        json_path = os.path.join(cfg.reports_dir, "migration_report.json")

        self.assertTrue(os.path.isfile(md_path))
        self.assertTrue(os.path.isfile(json_path))
        self.assertIn("migration_summary_md", report.artifacts)
        self.assertIn("migration_report_json", report.artifacts)

        # JSON should be valid
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("steps", data)
        self.assertIn("success", data)

    def test_no_reports_in_dry_run(self):
        cfg = MigrationConfig(
            input_dir=self.input_dir,
            dry_run=True,
            enabled_steps=["analyze"],
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()
        self.assertEqual(len(report.artifacts), 0)


# ---------------------------------------------------------------------------
# Terminal summary tests
# ---------------------------------------------------------------------------


class TestFormatMigrationSummary(unittest.TestCase):
    """Tests for the terminal summary formatter."""

    def test_basic_output(self):
        report = MigrationRunReport(
            input_dir="/in",
            output_dir="/out",
            source_version="tfs03",
            target_version="revscript",
            steps=[
                StepResult(name="convert", status=StepStatus.SUCCESS,
                           duration_seconds=1.5, summary="10 files converted"),
                StepResult(name="fix", status=StepStatus.FAILED,
                           duration_seconds=0.3, error="something broke"),
            ],
        )
        text = format_migration_summary(report)

        self.assertIn("Migration Summary", text)
        self.assertIn("convert", text)
        self.assertIn("SUCCESS", text)
        self.assertIn("FAILED", text)
        self.assertIn("1 succeeded", text)
        self.assertIn("1 failed", text)

    def test_dry_run_label(self):
        report = MigrationRunReport(dry_run=True)
        text = format_migration_summary(report)
        self.assertIn("DRY RUN", text)

    def test_all_success(self):
        report = MigrationRunReport(
            steps=[
                StepResult(name="a", status=StepStatus.SUCCESS),
                StepResult(name="b", status=StepStatus.SUCCESS),
            ],
        )
        text = format_migration_summary(report)
        self.assertIn("SUCCESS", text)
        self.assertNotIn("FAILED", text.split("Status:")[1])

    def test_backup_shown_in_summary(self):
        report = MigrationRunReport(
            backup_dir="/out_backup",
            steps=[StepResult(name="a", status=StepStatus.SUCCESS)],
        )
        text = format_migration_summary(report)
        self.assertIn("Backup", text)
        self.assertIn("/out_backup", text)

    def test_executive_summary_in_output(self):
        report = MigrationRunReport(
            steps=[
                StepResult(
                    name="convert",
                    status=StepStatus.SUCCESS,
                    outputs={"stats": {"lua_files_processed": 5, "xml_files_processed": 3}, "ttt_markers": 2},
                ),
                StepResult(
                    name="doctor",
                    status=StepStatus.SUCCESS,
                    outputs={"health_score": 90, "health_rating": "HEALTHY", "total_issues": 1},
                ),
            ],
        )
        text = format_migration_summary(report)
        self.assertIn("Executive Summary", text)
        self.assertIn("Files converted", text)
        self.assertIn("Health score", text)

    def test_artifacts_in_output(self):
        report = MigrationRunReport(
            artifacts={"migration_summary_md": "/out/reports/migration_summary.md"},
        )
        text = format_migration_summary(report)
        self.assertIn("Artifacts", text)
        self.assertIn("migration_summary_md", text)


# ---------------------------------------------------------------------------
# Markdown export tests
# ---------------------------------------------------------------------------


class TestFormatMigrationMarkdown(unittest.TestCase):
    """Tests for the markdown summary exporter."""

    def test_basic_markdown(self):
        report = MigrationRunReport(
            input_dir="/in",
            output_dir="/out",
            source_version="tfs03",
            target_version="revscript",
            steps=[
                StepResult(name="convert", status=StepStatus.SUCCESS,
                           duration_seconds=1.0, summary="5 files converted"),
            ],
        )
        md = format_migration_markdown(report)

        self.assertIn("# TTT Migration Summary", md)
        self.assertIn("| convert |", md)
        self.assertIn("SUCCESS", md)
        self.assertIn("tfs03", md)

    def test_markdown_executive_summary(self):
        report = MigrationRunReport(
            steps=[
                StepResult(
                    name="convert",
                    status=StepStatus.SUCCESS,
                    outputs={"stats": {"lua_files_processed": 3, "xml_files_processed": 2}, "ttt_markers": 1},
                ),
                StepResult(
                    name="doctor",
                    status=StepStatus.SUCCESS,
                    outputs={"health_score": 85, "health_rating": "WARNING", "total_issues": 2},
                ),
                StepResult(
                    name="fix",
                    status=StepStatus.SUCCESS,
                    outputs={"total_fixes": 7},
                ),
            ],
        )
        md = format_migration_markdown(report)
        self.assertIn("## Executive Summary", md)
        self.assertIn("Files converted", md)
        self.assertIn("Health score", md)
        self.assertIn("Auto-fixes", md)

    def test_markdown_artifacts(self):
        report = MigrationRunReport(
            artifacts={"docs_dir": "/out/docs", "conversion_report": "/out/conversion_report.txt"},
        )
        md = format_migration_markdown(report)
        self.assertIn("## Artifacts", md)
        self.assertIn("docs_dir", md)


# ---------------------------------------------------------------------------
# Integration test using examples/tfs03_input
# ---------------------------------------------------------------------------


# Detect if the examples/ directory exists (it should in the repo)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_EXAMPLES_INPUT = os.path.join(_PROJECT_ROOT, "examples", "tfs03_input")
_HAS_EXAMPLES = os.path.isdir(_EXAMPLES_INPUT)


@unittest.skipUnless(_HAS_EXAMPLES, "examples/tfs03_input not found")
class TestMigratorIntegration(unittest.TestCase):
    """End-to-end integration test using the examples/tfs03_input corpus."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="ttt_integ_")
        self.output_dir = os.path.join(self.tmpdir, "migrated")

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_full_migration_tfs03_to_revscript(self):
        """Run the full pipeline on examples/tfs03_input → revscript."""
        cfg = MigrationConfig(
            input_dir=_EXAMPLES_INPUT,
            output_dir=self.output_dir,
            source_version="tfs03",
            target_version="revscript",
            backup=True,
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()

        # Pipeline should complete
        self.assertIsNotNone(report.started_at)
        self.assertIsNotNone(report.finished_at)
        self.assertEqual(len(report.steps), 5)  # all default steps

        # Convert step should succeed with files processed
        convert_step = report.get_step("convert")
        self.assertIsNotNone(convert_step)
        self.assertEqual(convert_step.status, StepStatus.SUCCESS)
        self.assertGreater(report.files_converted, 0)

        # Output directory should have files
        self.assertTrue(os.path.isdir(self.output_dir))

        # Backup should exist
        self.assertTrue(os.path.isdir(cfg.backup_dir))

        # Reports should be written
        self.assertTrue(os.path.isfile(
            os.path.join(cfg.reports_dir, "migration_summary.md")
        ))
        self.assertTrue(os.path.isfile(
            os.path.join(cfg.reports_dir, "migration_report.json")
        ))

        # JSON report should be valid and round-trippable
        json_path = os.path.join(cfg.reports_dir, "migration_report.json")
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self.assertTrue(data["success"])
        self.assertGreater(data["files_converted"], 0)

        # Markdown summary should mention convert results
        md_path = os.path.join(cfg.reports_dir, "migration_summary.md")
        with open(md_path, "r", encoding="utf-8") as f:
            md_content = f.read()
        self.assertIn("Files converted", md_content)

    def test_dry_run_on_examples(self):
        """Dry-run should not write any output files."""
        cfg = MigrationConfig(
            input_dir=_EXAMPLES_INPUT,
            source_version="tfs03",
            target_version="revscript",
            dry_run=True,
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()

        self.assertFalse(os.path.exists(self.output_dir))
        self.assertEqual(len(report.artifacts), 0)

        # Should still have steps executed
        self.assertEqual(len(report.steps), 5)

    def test_partial_migration_only_convert_fix(self):
        """Running only convert+fix should produce converted files."""
        cfg = MigrationConfig(
            input_dir=_EXAMPLES_INPUT,
            output_dir=self.output_dir,
            source_version="tfs03",
            target_version="revscript",
            enabled_steps=["convert", "fix"],
            backup=False,
        )
        orch = MigrationOrchestrator(cfg)
        report = orch.run()

        self.assertEqual(len(report.steps), 2)
        self.assertFalse(os.path.exists(cfg.backup_dir))
        self.assertTrue(os.path.isdir(self.output_dir))


if __name__ == "__main__":
    unittest.main()
