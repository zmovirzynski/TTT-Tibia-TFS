"""
Tests for TTT Server Analyzer (Phase 3A).

Covers: stats, dead_code, duplicates, storage_scanner, item_usage, complexity, engine.
"""

import os
import json
import tempfile
import shutil
import textwrap
import unittest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_tree(base: str, files: dict):
    """Create a directory tree.  files = {relative_path: content}."""
    for rel_path, content in files.items():
        full = os.path.join(base, rel_path)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "w", encoding="utf-8") as f:
            f.write(content)


# ===================================================================
# Stats
# ===================================================================


class TestStats(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_basic_counts(self):
        _make_tree(
            self.tmpdir,
            {
                "actions/actions.xml": '<actions><action itemid="123" script="a.lua"/></actions>',
                "actions/scripts/a.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    doPlayerSendTextMessage(cid, 20, "hi")
                    return TRUE
                end
            """),
                "movements/movements.xml": "<movements></movements>",
                "globalevents/globalevents.xml": "<globalevents></globalevents>",
                "globalevents/scripts/start.lua": textwrap.dedent("""\
                function onStartup()
                    return TRUE
                end
            """),
            },
        )
        from ttt.analyzer.stats import collect_stats

        stats = collect_stats(self.tmpdir)
        self.assertEqual(stats.total_lua_files, 2)
        self.assertGreaterEqual(stats.total_xml_files, 2)
        self.assertEqual(stats.script_counts.actions, 1)
        self.assertEqual(stats.script_counts.globalevents, 1)
        self.assertGreater(stats.total_lines, 0)
        self.assertGreater(stats.total_code_lines, 0)
        self.assertEqual(stats.total_functions_defined, 2)

    def test_function_call_ranking(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/test.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    doPlayerSendTextMessage(cid, 20, "a")
                    doPlayerSendTextMessage(cid, 20, "b")
                    doPlayerSendTextMessage(cid, 20, "c")
                    getPlayerLevel(cid)
                    return true
                end
            """),
            },
        )
        from ttt.analyzer.stats import collect_stats

        stats = collect_stats(self.tmpdir)
        top = stats.top_functions(5)
        names = [n for n, _ in top]
        self.assertIn("doPlayerSendTextMessage", names)
        # doPlayerSendTextMessage should have count 3
        for name, count in top:
            if name == "doPlayerSendTextMessage":
                self.assertEqual(count, 3)

    def test_api_style_detection(self):
        _make_tree(
            self.tmpdir,
            {
                "old.lua": "function f() getPlayerLevel(cid) end",
                "new.lua": "function f() player:getLevel() end",
                "mixed.lua": "function f() getPlayerLevel(cid); player:addItem(1) end",
            },
        )
        from ttt.analyzer.stats import collect_stats

        stats = collect_stats(self.tmpdir)
        self.assertEqual(stats.api_style["procedural"], 1)
        self.assertEqual(stats.api_style["oop"], 1)
        self.assertEqual(stats.api_style["mixed"], 1)

    def test_as_dict(self):
        _make_tree(
            self.tmpdir,
            {
                "test.lua": "function onUse() return true end",
            },
        )
        from ttt.analyzer.stats import collect_stats

        stats = collect_stats(self.tmpdir)
        d = stats.as_dict()
        self.assertIn("script_counts", d)
        self.assertIn("top_functions", d)
        self.assertIn("api_style", d)

    def test_empty_directory(self):
        from ttt.analyzer.stats import collect_stats

        stats = collect_stats(self.tmpdir)
        self.assertEqual(stats.total_lua_files, 0)
        self.assertEqual(stats.script_counts.total, 0)


# ===================================================================
# Dead Code
# ===================================================================


class TestDeadCode(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_broken_xml_ref(self):
        _make_tree(
            self.tmpdir,
            {
                "actions/actions.xml": '<actions><action itemid="1" script="missing.lua"/></actions>',
                "actions/scripts/exists.lua": "-- exists",
            },
        )
        from ttt.analyzer.dead_code import detect_dead_code

        report = detect_dead_code(self.tmpdir)
        self.assertGreaterEqual(len(report.broken_xml_refs), 1)
        self.assertEqual(report.broken_xml_refs[0].script_ref, "missing.lua")

    def test_orphan_script(self):
        _make_tree(
            self.tmpdir,
            {
                "actions/actions.xml": '<actions><action itemid="1" script="used.lua"/></actions>',
                "actions/scripts/used.lua": "-- used",
                "actions/scripts/orphan.lua": "-- orphan",
            },
        )
        from ttt.analyzer.dead_code import detect_dead_code

        report = detect_dead_code(self.tmpdir)
        orphan_names = [os.path.basename(o.filepath) for o in report.orphan_scripts]
        self.assertIn("orphan.lua", orphan_names)
        self.assertNotIn("used.lua", orphan_names)

    def test_unused_function(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/test.lua": textwrap.dedent("""\
                function helperNeverCalled()
                    return 1
                end
                function onUse(cid)
                    return true
                end
            """),
            },
        )
        from ttt.analyzer.dead_code import detect_dead_code

        report = detect_dead_code(self.tmpdir)
        unused_names = [u.function_name for u in report.unused_functions]
        self.assertIn("helperNeverCalled", unused_names)
        # onUse is a known callback, should NOT be flagged
        self.assertNotIn("onUse", unused_names)

    def test_no_dead_code(self):
        _make_tree(
            self.tmpdir,
            {
                "actions/actions.xml": '<actions><action itemid="1" script="good.lua"/></actions>',
                "actions/scripts/good.lua": textwrap.dedent("""\
                function onUse(cid)
                    return true
                end
            """),
            },
        )
        from ttt.analyzer.dead_code import detect_dead_code

        report = detect_dead_code(self.tmpdir)
        self.assertEqual(len(report.broken_xml_refs), 0)
        self.assertEqual(len(report.orphan_scripts), 0)

    def test_as_dict(self):
        _make_tree(
            self.tmpdir,
            {
                "test.lua": "function onUse() return true end",
            },
        )
        from ttt.analyzer.dead_code import detect_dead_code

        report = detect_dead_code(self.tmpdir)
        d = report.as_dict()
        self.assertIn("orphan_scripts", d)
        self.assertIn("broken_xml_refs", d)
        self.assertIn("total_issues", d)


# ===================================================================
# Duplicates
# ===================================================================


class TestDuplicates(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_identical_scripts(self):
        code = textwrap.dedent("""\
            function onUse(cid, item)
                doPlayerSendTextMessage(cid, 20, "hello")
                return TRUE
            end
        """)
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": code,
                "scripts/b.lua": code,
            },
        )
        from ttt.analyzer.duplicates import detect_duplicates

        report = detect_duplicates(self.tmpdir)
        self.assertEqual(len(report.duplicate_scripts), 1)
        self.assertEqual(report.duplicate_scripts[0].count, 2)

    def test_no_duplicates(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "function a() return 1 end",
                "scripts/b.lua": "function b() return 2 end",
            },
        )
        from ttt.analyzer.duplicates import detect_duplicates

        report = detect_duplicates(self.tmpdir)
        self.assertEqual(len(report.duplicate_scripts), 0)

    def test_duplicate_talkaction_keyword(self):
        _make_tree(
            self.tmpdir,
            {
                "talkactions/talkactions.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <talkactions>
                    <talkaction words="!info" script="info1.lua"/>
                    <talkaction words="!info" script="info2.lua"/>
                </talkactions>
            """),
            },
        )
        from ttt.analyzer.duplicates import detect_duplicates

        report = detect_duplicates(self.tmpdir)
        dup_kw = [
            d
            for d in report.duplicate_registrations
            if d.reg_type == "talkaction-keyword"
        ]
        self.assertGreaterEqual(len(dup_kw), 1)
        self.assertEqual(dup_kw[0].key, "!info")

    def test_duplicate_action_itemid(self):
        _make_tree(
            self.tmpdir,
            {
                "actions/actions.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <actions>
                    <action itemid="2274" script="a.lua"/>
                    <action itemid="2274" script="b.lua"/>
                </actions>
            """),
            },
        )
        from ttt.analyzer.duplicates import detect_duplicates

        report = detect_duplicates(self.tmpdir)
        dup_ids = [
            d for d in report.duplicate_registrations if d.reg_type == "action-itemid"
        ]
        self.assertGreaterEqual(len(dup_ids), 1)

    def test_as_dict(self):
        _make_tree(
            self.tmpdir,
            {
                "test.lua": "function onUse() return true end",
            },
        )
        from ttt.analyzer.duplicates import detect_duplicates

        report = detect_duplicates(self.tmpdir)
        d = report.as_dict()
        self.assertIn("duplicate_scripts", d)
        self.assertIn("duplicate_registrations", d)


# ===================================================================
# Storage Scanner
# ===================================================================


class TestStorageScanner(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_detect_storage_ids(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/quest.lua": textwrap.dedent("""\
                function onUse(cid)
                    if getPlayerStorageValue(cid, 50001) == -1 then
                        doPlayerSetStorageValue(cid, 50001, 1)
                    end
                end
            """),
            },
        )
        from ttt.analyzer.storage_scanner import scan_storage

        report = scan_storage(self.tmpdir)
        self.assertEqual(report.total_unique_ids, 1)
        self.assertEqual(report.min_id, 50001)
        self.assertEqual(report.max_id, 50001)

    def test_detect_oop_storage(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/quest.lua": textwrap.dedent("""\
                function onUse(player)
                    if player:getStorageValue(60001) == -1 then
                        player:setStorageValue(60001, 1)
                    end
                end
            """),
            },
        )
        from ttt.analyzer.storage_scanner import scan_storage

        report = scan_storage(self.tmpdir)
        self.assertEqual(report.total_unique_ids, 1)
        ids = set(u.storage_id for u in report.all_usages)
        self.assertIn(60001, ids)

    def test_storage_conflict(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/quest1.lua": "player:getStorageValue(50001)",
                "scripts/quest2.lua": "player:setStorageValue(50001, 1)",
            },
        )
        from ttt.analyzer.storage_scanner import scan_storage

        report = scan_storage(self.tmpdir)
        self.assertGreaterEqual(len(report.conflicts), 1)
        self.assertEqual(report.conflicts[0].storage_id, 50001)

    def test_free_ranges(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "player:getStorageValue(10000)",
                "scripts/b.lua": "player:getStorageValue(10050)",
            },
        )
        from ttt.analyzer.storage_scanner import scan_storage

        report = scan_storage(self.tmpdir)
        self.assertGreater(len(report.free_ranges), 0)
        # There should be a gap between 10001-10049
        has_gap = any(r.start == 10001 and r.end == 10049 for r in report.free_ranges)
        self.assertTrue(has_gap)

    def test_no_storage(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "function onUse() return true end",
            },
        )
        from ttt.analyzer.storage_scanner import scan_storage

        report = scan_storage(self.tmpdir)
        self.assertEqual(report.total_unique_ids, 0)
        self.assertEqual(len(report.conflicts), 0)

    def test_as_dict(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "player:getStorageValue(10000)",
            },
        )
        from ttt.analyzer.storage_scanner import scan_storage

        report = scan_storage(self.tmpdir)
        d = report.as_dict()
        self.assertIn("total_unique_ids", d)
        self.assertIn("free_ranges", d)
        self.assertIn("all_ids", d)


# ===================================================================
# Item Usage
# ===================================================================


class TestItemUsage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_lua_item_ids(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/action.lua": textwrap.dedent("""\
                function onUse(player, item)
                    player:addItem(2160, 10)
                    player:addItem(2152, 5)
                end
            """),
            },
        )
        from ttt.analyzer.item_usage import scan_item_usage

        report = scan_item_usage(self.tmpdir)
        lua_ids = set(r.item_id for r in report.all_references if r.source == "lua")
        self.assertIn(2160, lua_ids)
        self.assertIn(2152, lua_ids)

    def test_xml_item_ids(self):
        _make_tree(
            self.tmpdir,
            {
                "actions/actions.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <actions>
                    <action itemid="2274" script="pot.lua"/>
                </actions>
            """),
                "actions/scripts/pot.lua": "-- empty",
            },
        )
        from ttt.analyzer.item_usage import scan_item_usage

        report = scan_item_usage(self.tmpdir)
        xml_ids = set(r.item_id for r in report.all_references if r.source == "xml")
        self.assertIn(2274, xml_ids)

    def test_lua_only_vs_xml_only(self):
        _make_tree(
            self.tmpdir,
            {
                "actions/actions.xml": '<actions><action itemid="2274" script="a.lua"/></actions>',
                "actions/scripts/a.lua": "player:addItem(9999, 1)",
            },
        )
        from ttt.analyzer.item_usage import scan_item_usage

        report = scan_item_usage(self.tmpdir)
        self.assertIn(9999, report.lua_only_ids)
        self.assertIn(2274, report.xml_only_ids)

    def test_empty(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "function f() return true end",
            },
        )
        from ttt.analyzer.item_usage import scan_item_usage

        report = scan_item_usage(self.tmpdir)
        self.assertEqual(report.total_unique_ids, 0)

    def test_as_dict(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "player:addItem(2160)",
            },
        )
        from ttt.analyzer.item_usage import scan_item_usage

        report = scan_item_usage(self.tmpdir)
        d = report.as_dict()
        self.assertIn("lua_only_ids", d)
        self.assertIn("xml_only_ids", d)


# ===================================================================
# Complexity
# ===================================================================


class TestComplexity(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_simple_function(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/simple.lua": textwrap.dedent("""\
                function onUse(cid)
                    return true
                end
            """),
            },
        )
        from ttt.analyzer.complexity import analyze_complexity

        report = analyze_complexity(self.tmpdir)
        self.assertEqual(report.total_functions, 1)
        func = report.files[0].functions[0]
        self.assertEqual(func.cyclomatic, 1)
        self.assertEqual(func.rating, "LOW")

    def test_complex_function(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/complex.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    if getPlayerLevel(cid) < 10 then
                        return false
                    end
                    if item.itemid == 1234 or item.itemid == 5678 then
                        if isPremium(cid) and getPlayerStorageValue(cid, 1000) == -1 then
                            doPlayerAddItem(cid, 2160, 1)
                        elseif getPlayerVocation(cid) == 1 or getPlayerVocation(cid) == 5 then
                            doPlayerAddItem(cid, 2152, 1)
                        end
                    end
                    for i = 1, 10 do
                        if i > 5 then
                            break
                        end
                    end
                    return true
                end
            """),
            },
        )
        from ttt.analyzer.complexity import analyze_complexity

        report = analyze_complexity(self.tmpdir)
        func = report.files[0].functions[0]
        self.assertGreater(func.cyclomatic, 5)

    def test_nesting_depth(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/nested.lua": textwrap.dedent("""\
                function onUse(cid)
                    if true then
                        if true then
                            if true then
                                return true
                            end
                        end
                    end
                end
            """),
            },
        )
        from ttt.analyzer.complexity import analyze_complexity

        report = analyze_complexity(self.tmpdir)
        func = report.files[0].functions[0]
        self.assertGreaterEqual(func.max_nesting, 3)

    def test_distribution(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "function f1() return true end",
                "scripts/b.lua": "function f2() return true end",
            },
        )
        from ttt.analyzer.complexity import analyze_complexity

        report = analyze_complexity(self.tmpdir)
        dist = report.distribution
        self.assertIn("LOW", dist)
        self.assertEqual(dist["LOW"], 2)

    def test_overall_rating(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "function f1() return true end",
            },
        )
        from ttt.analyzer.complexity import analyze_complexity

        report = analyze_complexity(self.tmpdir)
        self.assertEqual(report.overall_rating, "LOW")

    def test_refactoring_suggestion(self):
        """Complex function should get a suggestion."""
        lines = ["function bigFunc(cid)"]
        for i in range(25):
            lines.append(f"    if x{i} then doSomething{i}() end")
        lines.append("    return true")
        lines.append("end")
        _make_tree(
            self.tmpdir,
            {
                "scripts/big.lua": "\n".join(lines),
            },
        )
        from ttt.analyzer.complexity import analyze_complexity

        report = analyze_complexity(self.tmpdir)
        func = report.files[0].functions[0]
        self.assertGreater(func.cyclomatic, 10)
        self.assertNotEqual(func.suggestion, "")

    def test_as_dict(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "function f() return true end",
            },
        )
        from ttt.analyzer.complexity import analyze_complexity

        report = analyze_complexity(self.tmpdir)
        d = report.as_dict()
        self.assertIn("distribution", d)
        self.assertIn("overall_rating", d)
        self.assertIn("avg_complexity", d)


# ===================================================================
# Engine (integration)
# ===================================================================


class TestAnalyzeEngine(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_full_analysis(self):
        _make_tree(
            self.tmpdir,
            {
                "actions/actions.xml": '<actions><action itemid="2274" script="heal.lua"/></actions>',
                "actions/scripts/heal.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    if getPlayerLevel(cid) < 10 then
                        return false
                    end
                    doPlayerAddItem(cid, 2160, 1)
                    doPlayerSetStorageValue(cid, 50001, 1)
                    return TRUE
                end
            """),
            },
        )
        from ttt.analyzer.engine import AnalyzeEngine

        engine = AnalyzeEngine()
        report = engine.analyze(self.tmpdir)

        self.assertIsNotNone(report.stats)
        self.assertIsNotNone(report.dead_code)
        self.assertIsNotNone(report.duplicates)
        self.assertIsNotNone(report.storage)
        self.assertIsNotNone(report.item_usage)
        self.assertIsNotNone(report.complexity)

    def test_only_specific_modules(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "function f() return true end",
            },
        )
        from ttt.analyzer.engine import AnalyzeEngine

        engine = AnalyzeEngine(enabled_modules=["stats", "complexity"])
        report = engine.analyze(self.tmpdir)

        self.assertIsNotNone(report.stats)
        self.assertIsNotNone(report.complexity)
        self.assertIsNone(report.dead_code)
        self.assertIsNone(report.duplicates)
        self.assertIsNone(report.storage)

    def test_as_dict(self):
        _make_tree(
            self.tmpdir,
            {
                "scripts/a.lua": "function f() return true end",
            },
        )
        from ttt.analyzer.engine import AnalyzeEngine

        engine = AnalyzeEngine()
        report = engine.analyze(self.tmpdir)
        d = report.as_dict()
        self.assertIn("stats", d)
        self.assertIn("dead_code", d)
        self.assertIn("total_issues", d)


# ===================================================================
# Reporters
# ===================================================================


class TestReporters(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _make_tree(
            self.tmpdir,
            {
                "actions/actions.xml": '<actions><action itemid="2274" script="heal.lua"/></actions>',
                "actions/scripts/heal.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    if getPlayerLevel(cid) < 10 then
                        return false
                    end
                    doPlayerSetStorageValue(cid, 50001, 1)
                    return TRUE
                end
            """),
            },
        )
        from ttt.analyzer.engine import AnalyzeEngine

        engine = AnalyzeEngine()
        self.report = engine.analyze(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_text_format(self):
        from ttt.analyzer.engine import format_analysis_text

        text = format_analysis_text(self.report, no_color=True)
        self.assertIn("STATISTICS", text)
        self.assertIn("DEAD CODE", text)
        self.assertIn("COMPLEXITY", text)

    def test_text_format_no_color(self):
        from ttt.analyzer.engine import format_analysis_text

        text = format_analysis_text(self.report, no_color=True)
        # Should not contain ANSI codes
        self.assertNotIn("\033[", text)

    def test_json_format(self):
        from ttt.analyzer.engine import format_analysis_json

        j = format_analysis_json(self.report)
        data = json.loads(j)
        self.assertIn("stats", data)
        self.assertIn("dead_code", data)
        self.assertIn("complexity", data)

    def test_html_format(self):
        from ttt.analyzer.engine import format_analysis_html

        html = format_analysis_html(self.report)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Statistics", html)
        self.assertIn("TTT Server Analysis", html)


# ===================================================================
# Example Data (integration with real examples)
# ===================================================================


class TestExampleData(unittest.TestCase):
    """Test analyzer against the real example data."""

    EXAMPLES_DIR = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "examples", "tfs03_input"
    )

    @unittest.skipUnless(
        os.path.isdir(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "examples", "tfs03_input"
            )
        ),
        "Example data not present",
    )
    def test_analyze_examples(self):
        from ttt.analyzer.engine import AnalyzeEngine

        engine = AnalyzeEngine()
        report = engine.analyze(self.EXAMPLES_DIR)

        self.assertIsNotNone(report.stats)
        self.assertEqual(report.stats.total_lua_files, 9)
        self.assertGreater(report.stats.total_lines, 100)
        self.assertGreater(report.stats.total_functions_defined, 5)

    @unittest.skipUnless(
        os.path.isdir(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "examples", "tfs03_input"
            )
        ),
        "Example data not present",
    )
    def test_complexity_on_examples(self):
        from ttt.analyzer.complexity import analyze_complexity

        report = analyze_complexity(self.EXAMPLES_DIR)
        self.assertGreater(report.total_functions, 0)
        self.assertIn(report.overall_rating, ("LOW", "MEDIUM", "HIGH", "VERY HIGH"))

    @unittest.skipUnless(
        os.path.isdir(
            os.path.join(
                os.path.dirname(os.path.dirname(__file__)), "examples", "tfs03_input"
            )
        ),
        "Example data not present",
    )
    def test_storage_on_examples(self):
        from ttt.analyzer.storage_scanner import scan_storage

        report = scan_storage(self.EXAMPLES_DIR)
        self.assertGreater(report.total_unique_ids, 0)


if __name__ == "__main__":
    unittest.main()
