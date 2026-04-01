"""Tests for ttt.review — scanner, models, categorizer, and report formatters."""

import json
import os
import textwrap

import pytest

from ttt.review.models import ReviewCategory, ReviewFinding, ReviewReport
from ttt.review.scanner import ReviewScanner, categorize_marker
from ttt.review.report import format_review_text, format_review_html, format_review_json


# ═══════════════════════════════════════════════════════════════════════════
# Categorization
# ═══════════════════════════════════════════════════════════════════════════


class TestCategorizeMarker:
    """Tests for the categorize_marker() function."""

    def test_stub_marker(self):
        assert (
            categorize_marker("STUB: doCreateItemEx -- needs custom lib")
            == ReviewCategory.CUSTOM_FUNCTION
        )

    def test_removed_marker(self):
        assert (
            categorize_marker(
                "doSendAnimatedText removed in TFS 1.x. No direct equivalent."
            )
            == ReviewCategory.UNSUPPORTED_LEGACY
        )

    def test_no_equivalent_marker(self):
        assert (
            categorize_marker("No direct equivalent in TFS 1.x")
            == ReviewCategory.UNSUPPORTED_LEGACY
        )

    def test_deprecated_marker(self):
        assert (
            categorize_marker("This function is deprecated")
            == ReviewCategory.UNSUPPORTED_LEGACY
        )

    def test_auto_chained_marker(self):
        assert (
            categorize_marker("Returns Vocation object, auto-chained :getId()")
            == ReviewCategory.OBJECT_UNWRAPPING
        )

    def test_use_marker(self):
        # Contains :getId() → object unwrapping takes priority
        assert (
            categorize_marker("Use player:getVocation():getId() to check vocation type")
            == ReviewCategory.OBJECT_UNWRAPPING
        )

    def test_use_simple_marker(self):
        assert (
            categorize_marker("Use player:setStorageValue() instead")
            == ReviewCategory.API_REPLACEMENT
        )

    def test_in_1x_marker(self):
        # Contains :getTemplePosition() → object unwrapping
        assert (
            categorize_marker("In 1.x use player:getTown():getTemplePosition()")
            == ReviewCategory.OBJECT_UNWRAPPING
        )

    def test_in_1x_simple_marker(self):
        assert (
            categorize_marker("In 1.x use Combat object for area damage")
            == ReviewCategory.API_REPLACEMENT
        )

    def test_combat_object_marker(self):
        assert (
            categorize_marker("Use Combat object API in 1.x")
            == ReviewCategory.API_REPLACEMENT
        )

    def test_review_marker(self):
        assert (
            categorize_marker("Review this conversion for correctness")
            == ReviewCategory.CONFIDENCE_RISK
        )

    def test_verify_marker(self):
        assert (
            categorize_marker("Verify the parameter order")
            == ReviewCategory.CONFIDENCE_RISK
        )

    def test_function_body_not_found(self):
        assert (
            categorize_marker("Function body not found")
            == ReviewCategory.CUSTOM_FUNCTION
        )

    def test_general_fallback(self):
        assert (
            categorize_marker("Some unknown marker text xyz") == ReviewCategory.GENERAL
        )

    def test_condition_system_marker(self):
        assert (
            categorize_marker("In 1.x, feeding uses condition system.")
            == ReviewCategory.API_REPLACEMENT
        )


# ═══════════════════════════════════════════════════════════════════════════
# ReviewFinding model
# ═══════════════════════════════════════════════════════════════════════════


class TestReviewFinding:
    """Tests for ReviewFinding properties."""

    def test_short_text_strips_prefix(self):
        f = ReviewFinding(
            file="test.lua",
            line_number=1,
            marker_text="  -- TTT: Use foo:bar()",
            category=ReviewCategory.API_REPLACEMENT,
        )
        assert f.short_text == "Use foo:bar()"

    def test_short_text_strips_stub_prefix(self):
        f = ReviewFinding(
            file="test.lua",
            line_number=1,
            marker_text="-- TTT:STUB: doFoo -- needs lib",
            category=ReviewCategory.CUSTOM_FUNCTION,
        )
        assert f.short_text == "doFoo -- needs lib"

    def test_short_text_no_prefix(self):
        f = ReviewFinding(
            file="test.lua",
            line_number=1,
            marker_text="plain text",
            category=ReviewCategory.GENERAL,
        )
        assert f.short_text == "plain text"


# ═══════════════════════════════════════════════════════════════════════════
# ReviewReport model
# ═══════════════════════════════════════════════════════════════════════════


class TestReviewReport:
    """Tests for ReviewReport grouping and serialization."""

    @pytest.fixture
    def sample_report(self):
        return ReviewReport(
            scanned_dir="/tmp/out",
            total_files_scanned=5,
            findings=[
                ReviewFinding(
                    "a.lua", 10, "-- TTT: Use foo", ReviewCategory.API_REPLACEMENT
                ),
                ReviewFinding(
                    "a.lua", 20, "-- TTT: Review bar", ReviewCategory.CONFIDENCE_RISK
                ),
                ReviewFinding(
                    "b.lua",
                    5,
                    "-- TTT: removed in 1.x",
                    ReviewCategory.UNSUPPORTED_LEGACY,
                ),
                ReviewFinding(
                    "a.lua", 30, "-- TTT:STUB: baz", ReviewCategory.CUSTOM_FUNCTION
                ),
                ReviewFinding(
                    "c.lua",
                    1,
                    "-- TTT: auto-chained :getId()",
                    ReviewCategory.OBJECT_UNWRAPPING,
                ),
            ],
        )

    def test_total_markers(self, sample_report):
        assert sample_report.total_markers == 5

    def test_by_category(self, sample_report):
        cats = sample_report.by_category()
        assert len(cats[ReviewCategory.API_REPLACEMENT]) == 1
        assert len(cats[ReviewCategory.CONFIDENCE_RISK]) == 1
        assert len(cats[ReviewCategory.UNSUPPORTED_LEGACY]) == 1
        assert len(cats[ReviewCategory.CUSTOM_FUNCTION]) == 1
        assert len(cats[ReviewCategory.OBJECT_UNWRAPPING]) == 1

    def test_by_file(self, sample_report):
        files = sample_report.by_file()
        assert len(files["a.lua"]) == 3
        assert len(files["b.lua"]) == 1
        assert len(files["c.lua"]) == 1

    def test_top_blockers_sorted(self, sample_report):
        blockers = sample_report.top_blockers()
        assert blockers[0]["file"] == "a.lua"
        assert blockers[0]["count"] == 3
        assert len(blockers) == 3

    def test_top_blockers_limit(self, sample_report):
        blockers = sample_report.top_blockers(limit=2)
        assert len(blockers) == 2

    def test_to_dict_structure(self, sample_report):
        d = sample_report.to_dict()
        assert d["scanned_dir"] == "/tmp/out"
        assert d["total_files_scanned"] == 5
        assert d["total_markers"] == 5
        assert len(d["findings"]) == 5
        assert "by_category" in d
        assert "top_blockers" in d

    def test_to_dict_finding_fields(self, sample_report):
        f = sample_report.to_dict()["findings"][0]
        assert "file" in f
        assert "line" in f
        assert "marker" in f
        assert "category" in f
        assert "snippet" in f

    def test_empty_report(self):
        r = ReviewReport()
        assert r.total_markers == 0
        assert r.by_category() == {}
        assert r.by_file() == {}
        assert r.top_blockers() == []


# ═══════════════════════════════════════════════════════════════════════════
# Scanner
# ═══════════════════════════════════════════════════════════════════════════


class TestReviewScanner:
    """Tests for file/directory scanning."""

    def _write_lua(self, directory, name, content):
        path = os.path.join(directory, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(textwrap.dedent(content))
        return path

    def test_scan_single_file(self, tmp_path):
        lua = self._write_lua(
            str(tmp_path),
            "test.lua",
            """\
            local x = 1
            player:setVocation(2) -- TTT: Use player:getVocation():getId()
            local y = 2
        """,
        )
        scanner = ReviewScanner()
        report = scanner.scan(lua)
        assert report.total_files_scanned == 1
        assert report.total_markers == 1
        assert report.findings[0].category == ReviewCategory.OBJECT_UNWRAPPING
        assert report.findings[0].line_number == 2

    def test_scan_directory(self, tmp_path):
        self._write_lua(
            str(tmp_path),
            "a.lua",
            """\
            -- TTT: Use foo
            -- TTT: removed in 1.x
        """,
        )
        self._write_lua(
            str(tmp_path),
            "b.lua",
            """\
            -- TTT:STUB: bar -- custom
        """,
        )
        scanner = ReviewScanner()
        report = scanner.scan(str(tmp_path))
        assert report.total_files_scanned == 2
        assert report.total_markers == 3

    def test_scan_empty_directory(self, tmp_path):
        scanner = ReviewScanner()
        report = scanner.scan(str(tmp_path))
        assert report.total_files_scanned == 0
        assert report.total_markers == 0

    def test_scan_no_markers(self, tmp_path):
        self._write_lua(
            str(tmp_path),
            "clean.lua",
            """\
            local x = 1
            print("hello")
        """,
        )
        scanner = ReviewScanner()
        report = scanner.scan(str(tmp_path))
        assert report.total_files_scanned == 1
        assert report.total_markers == 0

    def test_scan_ignores_non_lua(self, tmp_path):
        txt = os.path.join(str(tmp_path), "notes.txt")
        with open(txt, "w") as f:
            f.write("-- TTT: this should be ignored\n")
        scanner = ReviewScanner()
        report = scanner.scan(str(tmp_path))
        assert report.total_markers == 0

    def test_scan_with_relative_paths(self, tmp_path):
        sub = tmp_path / "scripts"
        sub.mkdir()
        self._write_lua(
            str(sub),
            "action.lua",
            """\
            -- TTT: Use foo
        """,
        )
        scanner = ReviewScanner()
        report = scanner.scan_with_relative_paths(str(tmp_path))
        assert report.findings[0].file == os.path.join("scripts", "action.lua")

    def test_context_lines(self, tmp_path):
        self._write_lua(
            str(tmp_path),
            "ctx.lua",
            """\
            line1
            line2
            line3 -- TTT: marker here
            line4
            line5
        """,
        )
        scanner = ReviewScanner(context_lines=1)
        report = scanner.scan(str(tmp_path))
        snippet = report.findings[0].snippet
        assert "line2" in snippet
        assert "line3" in snippet
        assert "line4" in snippet
        # With context_lines=1, line1 should not be in snippet
        assert "line1" not in snippet

    def test_scan_nested_directories(self, tmp_path):
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        self._write_lua(str(sub), "deep.lua", "-- TTT: nested marker\n")
        scanner = ReviewScanner()
        report = scanner.scan(str(tmp_path))
        assert report.total_markers == 1


# ═══════════════════════════════════════════════════════════════════════════
# Report formatters
# ═══════════════════════════════════════════════════════════════════════════


class TestFormatReviewText:
    """Tests for terminal text output."""

    def test_empty_report(self):
        r = ReviewReport(scanned_dir="/tmp", total_files_scanned=3)
        text = format_review_text(r)
        assert "No review markers found" in text

    def test_includes_categories(self):
        r = ReviewReport(
            scanned_dir="/tmp",
            total_files_scanned=2,
            findings=[
                ReviewFinding(
                    "a.lua", 1, "-- TTT: Use foo", ReviewCategory.API_REPLACEMENT
                ),
                ReviewFinding(
                    "b.lua", 2, "-- TTT: removed", ReviewCategory.UNSUPPORTED_LEGACY
                ),
            ],
        )
        text = format_review_text(r)
        assert "API Replacement" in text
        assert "Unsupported Legacy" in text
        assert "Total markers:    2" in text

    def test_includes_top_blockers(self):
        r = ReviewReport(
            scanned_dir="/tmp",
            total_files_scanned=1,
            findings=[
                ReviewFinding("big.lua", 1, "-- TTT: a", ReviewCategory.GENERAL),
                ReviewFinding("big.lua", 2, "-- TTT: b", ReviewCategory.GENERAL),
            ],
        )
        text = format_review_text(r)
        assert "TOP BLOCKERS" in text
        assert "big.lua" in text


class TestFormatReviewJson:
    """Tests for JSON output."""

    def test_valid_json(self):
        r = ReviewReport(
            scanned_dir="/tmp",
            total_files_scanned=1,
            findings=[
                ReviewFinding(
                    "a.lua", 5, "-- TTT: Use bar", ReviewCategory.API_REPLACEMENT
                ),
            ],
        )
        data = json.loads(format_review_json(r))
        assert data["total_markers"] == 1
        assert data["findings"][0]["line"] == 5
        assert data["findings"][0]["category"] == "api-replacement"

    def test_empty_report_json(self):
        r = ReviewReport()
        data = json.loads(format_review_json(r))
        assert data["total_markers"] == 0
        assert data["findings"] == []


class TestFormatReviewHtml:
    """Tests for HTML output."""

    def test_produces_html(self):
        r = ReviewReport(
            scanned_dir="/tmp/out",
            total_files_scanned=2,
            findings=[
                ReviewFinding(
                    "x.lua",
                    3,
                    "-- TTT: Use Combat object",
                    ReviewCategory.API_REPLACEMENT,
                ),
            ],
        )
        html = format_review_html(r)
        assert "<!DOCTYPE html>" in html
        assert "TTT — Review Report" in html
        assert "x.lua" in html
        assert "API Replacement" in html

    def test_filter_buttons_present(self):
        r = ReviewReport(scanned_dir="/tmp", total_files_scanned=0)
        html = format_review_html(r)
        assert "filterCat" in html
        assert "Object Unwrapping" in html

    def test_empty_report_html(self):
        r = ReviewReport()
        html = format_review_html(r)
        assert "<!DOCTYPE html>" in html


# ═══════════════════════════════════════════════════════════════════════════
# Integration: scan real examples
# ═══════════════════════════════════════════════════════════════════════════


class TestReviewIntegration:
    """Integration tests scanning actual converted Lua files."""

    @pytest.fixture
    def converted_output(self, tmp_path):
        """Create a realistic converted output directory."""
        scripts = tmp_path / "scripts"
        scripts.mkdir()

        with open(scripts / "heal.lua", "w") as f:
            f.write(
                textwrap.dedent("""\
                function onUse(player, item, fromPosition, target, toPosition, isHotkey)
                    local voc = player:getVocation():getId() -- TTT: Returns Vocation object, auto-chained :getId() for numeric ID
                    if voc == 1 then
                        player:addHealth(100)
                    end
                    return true
                end
            """)
            )

        with open(scripts / "teleport.lua", "w") as f:
            f.write(
                textwrap.dedent("""\
                function onUse(player, item, fromPosition, target, toPosition, isHotkey)
                    player:teleportTo(Position(100, 200, 7)) -- TTT: Use player:getTown():getTemplePosition() for temple TP
                    doSendAnimatedText(pos, "woo") -- TTT: doSendAnimatedText removed in TFS 1.x. No direct equivalent.
                    return true
                end
            """)
            )

        with open(scripts / "combat.lua", "w") as f:
            f.write(
                textwrap.dedent("""\
                function onUse(player, item, fromPosition, target, toPosition, isHotkey)
                    doCombat(cid, combat, var) -- TTT:STUB: doCombat -- needs custom lib: Game.combat
                    return true
                end
            """)
            )

        return tmp_path

    def test_integration_scan(self, converted_output):
        scanner = ReviewScanner()
        report = scanner.scan_with_relative_paths(str(converted_output))
        assert report.total_files_scanned == 3
        assert report.total_markers == 4

    def test_integration_categories(self, converted_output):
        scanner = ReviewScanner()
        report = scanner.scan_with_relative_paths(str(converted_output))
        cats = report.by_category()
        assert ReviewCategory.OBJECT_UNWRAPPING in cats
        assert ReviewCategory.UNSUPPORTED_LEGACY in cats
        assert ReviewCategory.CUSTOM_FUNCTION in cats

    def test_integration_top_blockers(self, converted_output):
        scanner = ReviewScanner()
        report = scanner.scan_with_relative_paths(str(converted_output))
        blockers = report.top_blockers()
        # teleport.lua has 2 markers, should be top
        top_file = blockers[0]["file"]
        assert "teleport" in top_file
        assert blockers[0]["count"] == 2

    def test_integration_full_pipeline(self, converted_output):
        """End-to-end: scan → format text + JSON + HTML."""
        scanner = ReviewScanner()
        report = scanner.scan_with_relative_paths(str(converted_output))

        text = format_review_text(report)
        assert "Total markers:    4" in text

        data = json.loads(format_review_json(report))
        assert data["total_markers"] == 4

        html = format_review_html(report)
        assert "<!DOCTYPE html>" in html
        assert "teleport" in html
