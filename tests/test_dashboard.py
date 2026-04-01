"""Tests for ttt.dashboard — HTML dashboard generation."""

import os
import tempfile


from ttt.dashboard.generator import (
    DashboardGenerator,
    generate_dashboard,
    _status_badge,
    _confidence_badge,
)
from ttt.migrator.models import MigrationRunReport, StepResult, StepStatus, FileEntry


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _make_report(**overrides) -> MigrationRunReport:
    """Build a minimal MigrationRunReport for testing."""
    defaults = dict(
        input_dir="/tmp/input",
        output_dir="/tmp/output",
        source_version="tfs03",
        target_version="revscript",
    )
    defaults.update(overrides)
    return MigrationRunReport(**defaults)


def _make_successful_report() -> MigrationRunReport:
    """Build a report with realistic successful step results."""
    r = _make_report()
    r.steps = [
        StepResult(
            name="convert",
            status=StepStatus.SUCCESS,
            duration_seconds=1.5,
            summary="Converted 10 Lua files, 5 XML files, 0 errors",
            outputs={
                "stats": {"lua_files_processed": 10, "xml_files_processed": 5},
                "ttt_markers": 3,
            },
        ),
        StepResult(
            name="fix",
            status=StepStatus.SUCCESS,
            duration_seconds=0.4,
            summary="12 fixes applied across 8 files",
            outputs={"total_fixes": 12, "files_changed": 8},
        ),
        StepResult(
            name="analyze",
            status=StepStatus.SUCCESS,
            duration_seconds=0.2,
            summary="2 issues found",
            outputs={"total_issues": 2},
        ),
        StepResult(
            name="doctor",
            status=StepStatus.SUCCESS,
            duration_seconds=0.3,
            summary="Score: 85/100 (GOOD), 1 issues",
            outputs={"health_score": 85, "health_rating": "GOOD", "total_issues": 1},
        ),
        StepResult(
            name="docs",
            status=StepStatus.SUCCESS,
            duration_seconds=0.1,
            summary="25 entries documented",
            outputs={"total_entries": 25},
        ),
    ]
    r.artifacts = {
        "output_dir": "/tmp/output",
        "conversion_report": "/tmp/output/conversion_report.txt",
        "migration_summary_md": "/tmp/output/reports/migration_summary.md",
    }
    return r


# ═══════════════════════════════════════════════════════════════════════════
# DashboardGenerator
# ═══════════════════════════════════════════════════════════════════════════


class TestDashboardGenerator:
    """Tests for DashboardGenerator class."""

    def test_generate_returns_html_string(self):
        r = _make_successful_report()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "dashboard.html")
            html = gen.generate(path)
            assert isinstance(html, str)
            assert "<!DOCTYPE html>" in html

    def test_generate_writes_file(self):
        r = _make_successful_report()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "reports", "dashboard.html")
            gen.generate(path)
            assert os.path.exists(path)
            content = open(path, encoding="utf-8").read()
            assert "TTT Migration Dashboard" in content

    def test_html_contains_summary_cards(self):
        r = _make_successful_report()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "SUCCESS" in html
            assert "Files Converted" in html
            assert "Review Markers" in html
            assert "Health Score" in html
            assert "Doctor Issues" in html
            assert "Analysis Issues" in html
            assert "Auto-Fixes" in html

    def test_html_contains_step_rows(self):
        r = _make_successful_report()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "convert" in html
            assert "fix" in html
            assert "analyze" in html
            assert "doctor" in html
            assert "docs" in html
            assert "Pipeline Steps" in html

    def test_html_contains_artifacts(self):
        r = _make_successful_report()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "Artifacts" in html
            assert "conversion_report" in html

    def test_html_contains_trend_placeholder(self):
        r = _make_successful_report()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "Regression Trend" in html
            assert "trend-placeholder" in html

    def test_html_embeds_report_json(self):
        r = _make_successful_report()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "__TTT_REPORT__" in html

    def test_failed_report_shows_failed_status(self):
        r = _make_report()
        r.steps = [
            StepResult(name="convert", status=StepStatus.FAILED, error="boom"),
        ]
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "FAILED" in html
            assert "failed" in html  # CSS class

    def test_empty_report_generates_valid_html(self):
        r = _make_report()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "<!DOCTYPE html>" in html
            assert "</html>" in html

    def test_dry_run_report(self):
        r = _make_report(output_dir="", dry_run=True)
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "(dry-run)" in html

    def test_html_escapes_special_chars(self):
        r = _make_report(input_dir="/path/<special>&dir")
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "&lt;special&gt;" in html
            assert "&amp;dir" in html

    def test_warn_class_on_ttt_markers(self):
        r = _make_report()
        r.steps = [
            StepResult(
                name="convert",
                status=StepStatus.SUCCESS,
                outputs={"stats": {"lua_files_processed": 5}, "ttt_markers": 10},
            ),
        ]
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert ' warn"' in html or " warn" in html

    def test_warn_class_on_doctor_issues(self):
        r = _make_report()
        r.steps = [
            StepResult(
                name="doctor",
                status=StepStatus.SUCCESS,
                outputs={
                    "health_score": 60,
                    "health_rating": "FAIR",
                    "total_issues": 5,
                },
            ),
        ]
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "warn" in html


# ═══════════════════════════════════════════════════════════════════════════
# Convenience function
# ═══════════════════════════════════════════════════════════════════════════


class TestGenerateDashboard:
    """Tests for the generate_dashboard() convenience function."""

    def test_convenience_function_writes_file(self):
        r = _make_successful_report()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "dashboard.html")
            html = generate_dashboard(r, path)
            assert os.path.exists(path)
            assert "TTT Migration Dashboard" in html

    def test_convenience_function_returns_html(self):
        r = _make_report()
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "dashboard.html")
            result = generate_dashboard(r, path)
            assert isinstance(result, str)
            assert len(result) > 100


# ═══════════════════════════════════════════════════════════════════════════
# Status badge helper
# ═══════════════════════════════════════════════════════════════════════════


class TestStatusBadge:
    """Tests for _status_badge() helper."""

    def test_success_badge(self):
        badge = _status_badge(StepStatus.SUCCESS)
        assert "SUCCESS" in badge
        assert "badge" in badge
        assert "#a6e3a1" in badge

    def test_failed_badge(self):
        badge = _status_badge(StepStatus.FAILED)
        assert "FAILED" in badge
        assert "#f38ba8" in badge

    def test_skipped_badge(self):
        badge = _status_badge(StepStatus.SKIPPED)
        assert "SKIPPED" in badge

    def test_running_badge(self):
        badge = _status_badge(StepStatus.RUNNING)
        assert "RUNNING" in badge

    def test_pending_badge(self):
        badge = _status_badge(StepStatus.PENDING)
        assert "PENDING" in badge


# ═══════════════════════════════════════════════════════════════════════════
# Confidence badge helper
# ═══════════════════════════════════════════════════════════════════════════


class TestConfidenceBadge:
    """Tests for _confidence_badge() helper."""

    def test_high_badge(self):
        badge = _confidence_badge("HIGH")
        assert "HIGH" in badge
        assert "#a6e3a1" in badge

    def test_medium_badge(self):
        badge = _confidence_badge("MEDIUM")
        assert "MEDIUM" in badge
        assert "#f9e2af" in badge

    def test_low_badge(self):
        badge = _confidence_badge("LOW")
        assert "LOW" in badge
        assert "#fab387" in badge

    def test_review_badge(self):
        badge = _confidence_badge("REVIEW")
        assert "REVIEW" in badge
        assert "#f38ba8" in badge

    def test_case_insensitive(self):
        badge = _confidence_badge("high")
        assert "HIGH" in badge


# ═══════════════════════════════════════════════════════════════════════════
# File-level table
# ═══════════════════════════════════════════════════════════════════════════


class TestFileTable:
    """Tests for the per-file table in the dashboard."""

    def _make_report_with_files(self):
        r = _make_report()
        r.file_entries = [
            FileEntry(
                path="scripts/actions/heal.lua",
                file_type="lua",
                changes=5,
                ttt_markers=2,
                confidence="MEDIUM",
                has_diff=True,
            ),
            FileEntry(
                path="scripts/movements/tile.lua",
                file_type="lua",
                changes=3,
                ttt_markers=0,
                confidence="HIGH",
                has_diff=True,
            ),
            FileEntry(
                path="scripts/globalevents/startup.lua",
                file_type="lua",
                changes=1,
                ttt_markers=1,
                confidence="LOW",
                has_diff=False,
            ),
        ]
        return r

    def test_file_table_section_visible_with_files(self):
        r = self._make_report_with_files()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "Converted Files" in html
            assert "display:block" in html

    def test_file_table_hidden_without_files(self):
        r = _make_report()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "display:none" in html

    def test_file_table_contains_file_paths(self):
        r = self._make_report_with_files()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "scripts/actions/heal.lua" in html
            assert "scripts/movements/tile.lua" in html
            assert "scripts/globalevents/startup.lua" in html

    def test_file_table_confidence_badges(self):
        r = self._make_report_with_files()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "MEDIUM" in html
            assert "HIGH" in html
            assert "LOW" in html

    def test_file_table_marker_counts(self):
        r = self._make_report_with_files()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert 'class="marker-count warn"' in html
            assert 'class="marker-count clean"' in html

    def test_file_table_data_attributes(self):
        r = self._make_report_with_files()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert 'data-confidence="medium"' in html
            assert 'data-confidence="high"' in html
            assert 'data-confidence="low"' in html
            assert 'data-markers="2"' in html
            assert 'data-markers="0"' in html

    def test_file_table_diff_links(self):
        r = self._make_report_with_files()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "conversion_diff.html" in html

    def test_file_table_filter_controls(self):
        r = self._make_report_with_files()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "filterFiles" in html
            assert "toggleMarkers" in html
            assert "file-search" in html
            assert "filter-btn" in html

    def test_file_table_js_filtering_code(self):
        r = self._make_report_with_files()
        gen = DashboardGenerator(r)
        with tempfile.TemporaryDirectory() as td:
            html = gen.generate(os.path.join(td, "d.html"))
            assert "applyFilters" in html
            assert "activeConfidence" in html
