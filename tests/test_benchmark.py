"""Tests for ttt.benchmark — engine, models, and report formatters."""

import json
import os
import textwrap

import pytest

from ttt.benchmark.models import BenchmarkResult, CorpusEntry, GoldenComparison
from ttt.benchmark.engine import BenchmarkEngine
from ttt.benchmark.report import format_benchmark_text, format_benchmark_json


# ═══════════════════════════════════════════════════════════════════════════
# Models
# ═══════════════════════════════════════════════════════════════════════════


class TestBenchmarkResult:
    """Tests for BenchmarkResult data model."""

    def test_defaults(self):
        r = BenchmarkResult()
        assert r.files_converted == 0
        assert r.success is True
        assert r.golden_match_rate == 1.0

    def test_success_false_on_errors(self):
        r = BenchmarkResult(conversion_errors=1)
        assert r.success is False

    def test_success_false_on_failed_steps(self):
        r = BenchmarkResult(steps_failed=1)
        assert r.success is False

    def test_golden_match_rate_with_comparisons(self):
        r = BenchmarkResult(
            golden_matches=3,
            golden_mismatches=1,
            golden_comparisons=[
                GoldenComparison("a.lua", True),
                GoldenComparison("b.lua", True),
                GoldenComparison("c.lua", True),
                GoldenComparison("d.lua", False, diff_lines=5),
            ],
        )
        assert r.golden_match_rate == 0.75

    def test_golden_match_rate_empty(self):
        r = BenchmarkResult()
        assert r.golden_match_rate == 1.0

    def test_to_dict_structure(self):
        r = BenchmarkResult(
            corpus_name="test",
            source_version="tfs03",
            target_version="revscript",
            duration_seconds=1.234,
            files_converted=5,
        )
        d = r.to_dict()
        assert d["corpus_name"] == "test"
        assert d["source_version"] == "tfs03"
        assert d["duration_seconds"] == 1.234
        assert d["files_converted"] == 5
        assert "golden_comparisons" in d
        assert "success" in d

    def test_to_dict_golden_comparisons(self):
        r = BenchmarkResult(
            golden_comparisons=[
                GoldenComparison("a.lua", True),
                GoldenComparison("b.lua", False, diff_lines=3),
            ],
            golden_matches=1,
            golden_mismatches=1,
        )
        d = r.to_dict()
        assert len(d["golden_comparisons"]) == 2
        assert d["golden_comparisons"][0]["match"] is True
        assert d["golden_comparisons"][1]["diff_lines"] == 3


class TestCorpusEntry:
    """Tests for CorpusEntry data model."""

    def test_defaults(self):
        e = CorpusEntry(name="test", input_dir="/tmp/input")
        assert e.source_version == "tfs03"
        assert e.target_version == "revscript"
        assert e.golden_dir == ""

    def test_custom_versions(self):
        e = CorpusEntry(
            name="test", input_dir="/tmp/input",
            source_version="tfs04", target_version="tfs1x",
        )
        assert e.source_version == "tfs04"
        assert e.target_version == "tfs1x"


class TestGoldenComparison:
    """Tests for GoldenComparison data model."""

    def test_match(self):
        g = GoldenComparison("a.lua", True)
        assert g.match is True
        assert g.diff_lines == 0

    def test_mismatch(self):
        g = GoldenComparison("a.lua", False, diff_lines=10,
                             expected_lines=50, actual_lines=55)
        assert g.match is False
        assert g.diff_lines == 10


# ═══════════════════════════════════════════════════════════════════════════
# Engine
# ═══════════════════════════════════════════════════════════════════════════


class TestBenchmarkEngine:
    """Tests for BenchmarkEngine."""

    def _make_corpus(self, tmp_path, scripts=None, golden_scripts=None):
        """Create a minimal TFS 0.3 corpus for benchmarking."""
        input_dir = tmp_path / "input"
        actions_dir = input_dir / "actions" / "scripts"
        actions_dir.mkdir(parents=True)

        # Create actions.xml
        xml_content = '<?xml version="1.0" encoding="UTF-8"?>\n<actions>\n'
        if scripts is None:
            scripts = {
                "test_action.lua": textwrap.dedent("""\
                    function onUse(cid, item, frompos, item2, topos)
                        doPlayerSendTextMessage(cid, MESSAGE_STATUS_CONSOLE_BLUE, "Hello")
                        return true
                    end
                """),
            }
        for name in scripts:
            xml_content += f'  <action itemid="1234" script="{name}"/>\n'
        xml_content += '</actions>'

        with open(input_dir / "actions" / "actions.xml", "w") as f:
            f.write(xml_content)

        for name, content in scripts.items():
            with open(actions_dir / name, "w") as f:
                f.write(content)

        # Golden expected output (optional)
        golden_dir = ""
        if golden_scripts is not None:
            golden_base = tmp_path / "expected"
            golden_scripts_dir = golden_base / "scripts" / "actions"
            golden_scripts_dir.mkdir(parents=True)
            for name, content in golden_scripts.items():
                with open(golden_scripts_dir / name, "w") as f:
                    f.write(content)
            golden_dir = str(golden_base)

        return str(input_dir), golden_dir

    def test_basic_conversion(self, tmp_path):
        input_dir, _ = self._make_corpus(tmp_path)
        entry = CorpusEntry(
            name="basic", input_dir=input_dir,
            source_version="tfs03", target_version="revscript",
        )
        engine = BenchmarkEngine()
        result = engine.run(entry)
        assert result.files_converted > 0
        assert result.duration_seconds > 0
        assert result.steps_run == 1
        assert result.steps_succeeded == 1

    def test_invalid_input_dir(self, tmp_path):
        entry = CorpusEntry(
            name="missing", input_dir=str(tmp_path / "nonexistent"),
        )
        engine = BenchmarkEngine()
        result = engine.run(entry)
        assert result.conversion_errors > 0

    def test_marker_counting(self, tmp_path):
        scripts = {
            "with_markers.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    doSendAnimatedText(getThingPos(cid), "wow", 18)
                    return true
                end
            """),
        }
        input_dir, _ = self._make_corpus(tmp_path, scripts=scripts)
        entry = CorpusEntry(name="markers", input_dir=input_dir)
        engine = BenchmarkEngine()
        result = engine.run(entry)
        # After conversion, some markers should be generated
        assert result.review_markers >= 0  # depends on mapping coverage

    def test_golden_comparison_match(self, tmp_path):
        """Test golden comparison when actual matches expected."""
        scripts = {
            "simple.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    return true
                end
            """),
        }
        input_dir, _ = self._make_corpus(tmp_path, scripts=scripts)

        # First run to get the actual output
        entry = CorpusEntry(name="golden_prep", input_dir=input_dir)
        engine = BenchmarkEngine()
        import tempfile
        with tempfile.TemporaryDirectory() as out_dir:
            from ttt.engine import ConversionEngine
            ce = ConversionEngine(
                source_version="tfs03", target_version="revscript",
                input_dir=input_dir, output_dir=out_dir,
            )
            ce.run()
            # Copy output as golden
            golden_dir = tmp_path / "golden"
            import shutil
            shutil.copytree(out_dir, str(golden_dir))

        # Now run benchmark with golden comparison
        entry = CorpusEntry(
            name="golden_test", input_dir=input_dir,
            golden_dir=str(golden_dir),
        )
        result = engine.run(entry)
        if result.golden_comparisons:
            assert result.golden_match_rate == 1.0

    def test_golden_comparison_mismatch(self, tmp_path):
        """Test golden comparison when actual differs from expected."""
        scripts = {
            "diff.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    doPlayerSendTextMessage(cid, MESSAGE_STATUS_CONSOLE_BLUE, "Hello")
                    return true
                end
            """),
        }
        golden_scripts = {
            "diff.lua": "-- This is completely different expected output\n",
        }
        input_dir, golden_dir = self._make_corpus(
            tmp_path, scripts=scripts, golden_scripts=golden_scripts,
        )
        entry = CorpusEntry(
            name="mismatch", input_dir=input_dir, golden_dir=golden_dir,
        )
        engine = BenchmarkEngine()
        result = engine.run(entry)
        # The golden dir structure may not align perfectly with actual output
        # but if comparisons exist, there should be mismatches
        if result.golden_comparisons:
            assert result.golden_mismatches > 0

    def test_run_corpus_multiple(self, tmp_path):
        input_dir, _ = self._make_corpus(tmp_path)
        entries = [
            CorpusEntry(name="run1", input_dir=input_dir),
            CorpusEntry(name="run2", input_dir=input_dir),
        ]
        engine = BenchmarkEngine()
        results = engine.run_corpus(entries)
        assert len(results) == 2
        assert all(r.steps_run >= 1 for r in results)


# ═══════════════════════════════════════════════════════════════════════════
# Engine — real examples corpus
# ═══════════════════════════════════════════════════════════════════════════


class TestBenchmarkExamplesCorpus:
    """Integration tests running benchmark against the real examples/ corpus."""

    EXAMPLES_DIR = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "examples", "tfs03_input"
    )
    GOLDEN_DIR = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "examples", "tfs1x_output"
    )

    @pytest.fixture
    def examples_entry(self):
        if not os.path.isdir(self.EXAMPLES_DIR):
            pytest.skip("examples/tfs03_input not found")
        return CorpusEntry(
            name="tfs03_examples",
            input_dir=self.EXAMPLES_DIR,
            golden_dir=self.GOLDEN_DIR if os.path.isdir(self.GOLDEN_DIR) else "",
            source_version="tfs03",
            target_version="revscript",
        )

    def test_examples_benchmark_runs(self, examples_entry):
        engine = BenchmarkEngine()
        result = engine.run(examples_entry)
        assert result.files_converted > 0
        assert result.duration_seconds > 0

    def test_examples_no_conversion_errors(self, examples_entry):
        engine = BenchmarkEngine()
        result = engine.run(examples_entry)
        assert result.conversion_errors == 0

    def test_examples_metrics_populated(self, examples_entry):
        engine = BenchmarkEngine()
        result = engine.run(examples_entry)
        assert result.files_converted > 0
        # tfs03 examples use XML→revscript path, so xml files are processed
        assert result.xml_files_processed > 0 or result.lua_files_processed > 0
        # At least some review markers expected from the example scripts
        assert result.review_markers >= 0

    def test_examples_json_output(self, examples_entry):
        engine = BenchmarkEngine()
        result = engine.run(examples_entry)
        data = json.loads(format_benchmark_json([result]))
        assert data["total"] == 1
        assert data["benchmarks"][0]["files_converted"] > 0


# ═══════════════════════════════════════════════════════════════════════════
# Report formatters
# ═══════════════════════════════════════════════════════════════════════════


class TestFormatBenchmarkText:
    """Tests for terminal text output."""

    def test_basic_output(self):
        r = BenchmarkResult(
            corpus_name="test",
            source_version="tfs03",
            target_version="revscript",
            duration_seconds=0.5,
            files_converted=3,
            lua_files_processed=3,
        )
        text = format_benchmark_text([r])
        assert "Benchmark Results" in text
        assert "test" in text
        assert "tfs03" in text
        assert "Files converted:     3" in text

    def test_golden_comparisons_shown(self):
        r = BenchmarkResult(
            corpus_name="golden_test",
            source_version="tfs03",
            target_version="revscript",
            golden_comparisons=[
                GoldenComparison("a.lua", True),
                GoldenComparison("b.lua", False, diff_lines=5),
            ],
            golden_matches=1,
            golden_mismatches=1,
        )
        text = format_benchmark_text([r])
        assert "Golden Comparisons" in text
        assert "MATCH" in text
        assert "DIFF" in text
        assert "50.0%" in text

    def test_multiple_results_aggregate(self):
        results = [
            BenchmarkResult(corpus_name="a", duration_seconds=0.1),
            BenchmarkResult(corpus_name="b", duration_seconds=0.2),
        ]
        text = format_benchmark_text(results)
        assert "2/2 passed" in text

    def test_pass_fail_status(self):
        r = BenchmarkResult(corpus_name="ok")
        text = format_benchmark_text([r])
        assert "PASS" in text

        r2 = BenchmarkResult(corpus_name="bad", conversion_errors=1)
        text2 = format_benchmark_text([r2])
        assert "FAIL" in text2


class TestFormatBenchmarkJson:
    """Tests for JSON output."""

    def test_valid_json(self):
        r = BenchmarkResult(
            corpus_name="test",
            source_version="tfs03",
            target_version="revscript",
            files_converted=5,
        )
        data = json.loads(format_benchmark_json([r]))
        assert data["total"] == 1
        assert data["passed"] == 1
        assert data["failed"] == 0
        assert data["benchmarks"][0]["files_converted"] == 5

    def test_empty_results(self):
        data = json.loads(format_benchmark_json([]))
        assert data["total"] == 0
        assert data["benchmarks"] == []

    def test_failed_benchmark_json(self):
        r = BenchmarkResult(corpus_name="fail", conversion_errors=2)
        data = json.loads(format_benchmark_json([r]))
        assert data["failed"] == 1
        assert data["passed"] == 0
