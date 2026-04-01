"""Tests for post-Sprint 7 backlog features.

Covers:
1. ExplainReport (ttt convert --explain)
2. Per-rule confidence scoring
3. AST-assisted guidance
4. Benchmark trend reports
5. NPC conversation analyzer
"""

import json
import os
import sys
import tempfile
import shutil
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ttt.converters.explain import ExplainEntry, ExplainReport
from ttt.converters.rule_confidence import rule_confidence, aggregate_confidence
from ttt.converters.ast_guidance import (
    GuidanceEntry, GuidanceReport, analyze_converted_code,
)
from ttt.analyzer.npc_analyzer import NPCConversationAnalyzer, NPCData


# ====================================================================
# 1. ExplainReport Tests
# ====================================================================

class TestExplainEntry(unittest.TestCase):

    def test_default_values(self):
        e = ExplainEntry()
        self.assertEqual(e.file, "")
        self.assertEqual(e.line, 0)
        self.assertEqual(e.stage, "")
        self.assertEqual(e.confidence, 1.0)

    def test_custom_values(self):
        e = ExplainEntry(
            file="test.lua", line=10, stage="function",
            original="doPlayerAddItem(cid, 2160, 1)",
            transformed="player:addItem(2160, 1)",
            rule="doPlayerAddItem", reasoning="Method rename",
            confidence=0.95,
        )
        self.assertEqual(e.file, "test.lua")
        self.assertEqual(e.line, 10)
        self.assertEqual(e.stage, "function")
        self.assertIn("doPlayerAddItem", e.original)


class TestExplainReport(unittest.TestCase):

    def _make_report(self):
        report = ExplainReport()
        report.add(ExplainEntry(file="a.lua", line=1, stage="function"))
        report.add(ExplainEntry(file="a.lua", line=5, stage="constant"))
        report.add(ExplainEntry(file="b.lua", line=2, stage="function"))
        return report

    def test_add_entries(self):
        report = self._make_report()
        self.assertEqual(len(report.entries), 3)

    def test_by_file(self):
        report = self._make_report()
        by_file = report.by_file
        self.assertEqual(len(by_file["a.lua"]), 2)
        self.assertEqual(len(by_file["b.lua"]), 1)

    def test_by_stage(self):
        report = self._make_report()
        by_stage = report.by_stage
        self.assertEqual(by_stage["function"], 2)
        self.assertEqual(by_stage["constant"], 1)

    def test_to_dict(self):
        report = self._make_report()
        d = report.to_dict()
        self.assertEqual(d["total_transformations"], 3)
        self.assertIn("entries", d)
        self.assertIn("by_stage", d)

    def test_to_text_contains_header(self):
        report = self._make_report()
        text = report.to_text()
        self.assertIn("Explain Report", text)
        self.assertIn("Total transformations: 3", text)

    def test_write_creates_files(self):
        report = self._make_report()
        with tempfile.TemporaryDirectory() as tmpdir:
            report.write(tmpdir)
            txt_path = os.path.join(tmpdir, "conversion_explain.txt")
            json_path = os.path.join(tmpdir, "conversion_explain.json")
            self.assertTrue(os.path.exists(txt_path))
            self.assertTrue(os.path.exists(json_path))
            with open(json_path) as f:
                data = json.load(f)
            self.assertEqual(data["total_transformations"], 3)

    def test_empty_report(self):
        report = ExplainReport()
        self.assertEqual(len(report.entries), 0)
        self.assertEqual(report.by_stage, {})
        self.assertEqual(report.by_file, {})
        text = report.to_text()
        self.assertIn("0", text)


# ====================================================================
# 2. Per-Rule Confidence Tests
# ====================================================================

class TestRuleConfidence(unittest.TestCase):

    def test_simple_method(self):
        mapping = {"method": "getHealth"}
        self.assertEqual(rule_confidence(mapping), 1.0)

    def test_stub_mapping(self):
        mapping = {"stub": True, "method": "someMethod"}
        self.assertEqual(rule_confidence(mapping), 0.5)

    def test_chain_mapping(self):
        mapping = {"method": "getName", "chain": ":getId()"}
        self.assertEqual(rule_confidence(mapping), 0.9)

    def test_static_mapping(self):
        mapping = {"static": True, "method": "create"}
        self.assertEqual(rule_confidence(mapping), 0.85)

    def test_wrapper_mapping(self):
        mapping = {"wrapper": "some_wrapper", "method": "doThing"}
        self.assertEqual(rule_confidence(mapping), 0.85)

    def test_custom_safe(self):
        mapping = {"custom": "type_check"}
        self.assertEqual(rule_confidence(mapping), 0.85)

    def test_custom_generic(self):
        mapping = {"custom": "some_handler"}
        self.assertEqual(rule_confidence(mapping), 0.7)

    def test_custom_passthrough(self):
        mapping = {"custom": "passthrough_item"}
        self.assertEqual(rule_confidence(mapping), 0.6)

    def test_note_with_ttt(self):
        mapping = {"method": "doSomething", "note": "-- TTT: check manually"}
        self.assertEqual(rule_confidence(mapping), 0.7)

    def test_note_with_ttt_and_chain(self):
        mapping = {"method": "doSomething", "chain": ":func()", "note": "-- TTT: verify"}
        self.assertEqual(rule_confidence(mapping), 0.65)

    def test_no_method(self):
        mapping = {}
        self.assertEqual(rule_confidence(mapping), 0.6)


class TestAggregateConfidence(unittest.TestCase):

    def test_empty_list(self):
        self.assertEqual(aggregate_confidence([]), 1.0)

    def test_all_perfect(self):
        result = aggregate_confidence([1.0, 1.0, 1.0])
        self.assertAlmostEqual(result, 1.0)

    def test_all_low(self):
        result = aggregate_confidence([0.5, 0.5, 0.5])
        self.assertAlmostEqual(result, 0.5)

    def test_mixed_scores(self):
        result = aggregate_confidence([1.0, 0.5])
        self.assertGreater(result, 0.5)
        self.assertLess(result, 1.0)

    def test_single_score(self):
        result = aggregate_confidence([0.85])
        self.assertAlmostEqual(result, 0.85)

    def test_low_drags_more(self):
        # A single low score should drag down more than a single high raises
        high_mix = aggregate_confidence([0.9, 0.9, 0.5])
        self.assertLess(high_mix, 0.9)


# ====================================================================
# 3. AST Guidance Tests
# ====================================================================

class TestGuidanceEntry(unittest.TestCase):

    def test_default_values(self):
        e = GuidanceEntry()
        self.assertEqual(e.severity, "info")
        self.assertEqual(e.category, "")

    def test_custom_values(self):
        e = GuidanceEntry(
            file="test.lua", line=5, severity="warning",
            category="type_safety", title="Nil access",
        )
        self.assertEqual(e.severity, "warning")
        self.assertEqual(e.category, "type_safety")


class TestGuidanceReport(unittest.TestCase):

    def _make_report(self):
        r = GuidanceReport()
        r.add(GuidanceEntry(severity="warning", category="type_safety"))
        r.add(GuidanceEntry(severity="info", category="pattern"))
        r.add(GuidanceEntry(severity="warning", category="scope"))
        return r

    def test_add_entries(self):
        r = self._make_report()
        self.assertEqual(len(r.entries), 3)

    def test_by_severity(self):
        r = self._make_report()
        self.assertEqual(r.by_severity["warning"], 2)
        self.assertEqual(r.by_severity["info"], 1)

    def test_by_category(self):
        r = self._make_report()
        self.assertEqual(r.by_category["type_safety"], 1)
        self.assertEqual(r.by_category["pattern"], 1)
        self.assertEqual(r.by_category["scope"], 1)

    def test_to_dict(self):
        r = self._make_report()
        d = r.to_dict()
        self.assertEqual(d["total"], 3)
        self.assertIn("entries", d)

    def test_to_text(self):
        r = self._make_report()
        text = r.to_text()
        self.assertIn("Guidance Report", text)

    def test_empty_report(self):
        r = GuidanceReport()
        self.assertEqual(len(r.entries), 0)
        self.assertEqual(r.by_severity, {})


class TestGuidanceAnalysis(unittest.TestCase):

    def test_nil_safety_detection(self):
        code = """
local hp = Player(cid):getHealth()
"""
        report = GuidanceReport()
        analyze_converted_code(code, "", "test.lua", report)
        nil_entries = [e for e in report.entries if e.category == "type_safety"
                       and "nil" in e.title.lower()]
        self.assertTrue(len(nil_entries) >= 1)

    def test_nil_safety_skips_checked(self):
        code = """
local player = Player(cid)
if not Player(cid) then return end
local hp = Player(cid):getHealth()
"""
        report = GuidanceReport()
        analyze_converted_code(code, "", "test.lua", report)
        nil_entries = [e for e in report.entries if e.category == "type_safety"
                       and "nil" in e.title.lower()]
        # Should not flag since there's a nil check
        self.assertEqual(len(nil_entries), 0)

    def test_deprecated_pattern_detection(self):
        code = """
doPlayerSendTextMessage(cid, 22, "hello")
"""
        report = GuidanceReport()
        analyze_converted_code(code, "", "test.lua", report)
        compat_entries = [e for e in report.entries if e.category == "compat"]
        self.assertTrue(len(compat_entries) >= 1)

    def test_storage_usage_warning(self):
        # Many hard-coded storage keys (uses TFS 1.x OOP syntax)
        lines = [f'player:setStorageValue({1000 + i}, 1)' for i in range(15)]
        code = "\n".join(lines)
        report = GuidanceReport()
        analyze_converted_code(code, "", "test.lua", report)
        storage_entries = [e for e in report.entries if e.category == "pattern"
                           and "storage" in e.title.lower()]
        self.assertTrue(len(storage_entries) >= 1)

    def test_type_coercion_detection(self):
        # Pattern matches :getVocation():getId() == "string"
        code = """
local voc = player:getVocation():getId() == "knight"
"""
        report = GuidanceReport()
        analyze_converted_code(code, "", "test.lua", report)
        type_entries = [e for e in report.entries if e.category == "type_safety"
                        and "vocation" in e.title.lower()]
        self.assertTrue(len(type_entries) >= 1)

    def test_event_registration_detection(self):
        # Must use the RevScript handler pattern: function X.onY()
        code = """
function action.onUse(player, item, fromPosition, target, toPosition)
    return true
end
"""
        report = GuidanceReport()
        analyze_converted_code(code, "", "test.lua", report)
        reg_entries = [e for e in report.entries if e.category == "pattern"
                       and "registration" in e.title.lower()]
        self.assertTrue(len(reg_entries) >= 1)

    def test_clean_code_no_warnings(self):
        code = """
local player = Player(cid)
if not player then return false end
player:sendTextMessage(MESSAGE_STATUS_DEFAULT, "Hello")
return true
"""
        report = GuidanceReport()
        analyze_converted_code(code, "", "test.lua", report)
        # May have some info entries, but should have few warnings
        warnings = [e for e in report.entries if e.severity == "warning"]
        self.assertLessEqual(len(warnings), 1)


# ====================================================================
# 4. Benchmark Trend Tests
# ====================================================================

class TestBenchmarkTrend(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.history_path = os.path.join(self.tmpdir, "history.json")

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _make_history(self, n=3):
        history = []
        for i in range(n):
            history.append({
                "timestamp": f"2025-01-0{i + 1}T10:00:00",
                "label": f"run-{i + 1}",
                "files_converted": 10 + i,
                "review_markers": max(0, 5 - i),
                "conversion_errors": 0,
                "duration_seconds": 1.5 + i * 0.1,
                "golden_match_rate": 0.9 + i * 0.02,
                "success": True,
            })
        with open(self.history_path, "w") as f:
            json.dump(history, f)
        return history

    def test_load_empty_history(self):
        from ttt.benchmark.trend import load_history
        history = load_history(os.path.join(self.tmpdir, "nonexistent.json"))
        self.assertEqual(history, [])

    def test_load_history(self):
        from ttt.benchmark.trend import load_history
        self._make_history()
        history = load_history(self.history_path)
        self.assertEqual(len(history), 3)

    def test_format_trend_text_empty(self):
        from ttt.benchmark.trend import format_trend_text
        text = format_trend_text([])
        self.assertIn("No benchmark history", text)

    def test_format_trend_text_content(self):
        from ttt.benchmark.trend import format_trend_text
        history = self._make_history()
        text = format_trend_text(history)
        self.assertIn("Trend Report", text)
        self.assertIn("3", text)  # Total runs
        self.assertIn("2025-01-01", text)
        # With 3 runs, should have deltas section
        self.assertIn("Delta", text)

    def test_format_trend_json(self):
        from ttt.benchmark.trend import format_trend_json
        history = self._make_history()
        raw = format_trend_json(history)
        data = json.loads(raw)
        self.assertEqual(data["total_runs"], 3)
        self.assertEqual(len(data["history"]), 3)

    def test_generate_trend_html_empty(self):
        from ttt.benchmark.trend import generate_trend_html
        html = generate_trend_html([])
        self.assertIn("No benchmark history", html)

    def test_generate_trend_html_content(self):
        from ttt.benchmark.trend import generate_trend_html
        history = self._make_history()
        html = generate_trend_html(history)
        self.assertIn("Trend Report", html)
        self.assertIn("chart", html.lower())
        self.assertIn("run-1", html)

    def test_format_trend_text_single_run(self):
        from ttt.benchmark.trend import format_trend_text
        history = self._make_history(1)
        text = format_trend_text(history)
        self.assertIn("Total runs: 1", text)
        # No deltas with only 1 run
        self.assertNotIn("Deltas", text)


# ====================================================================
# 5. NPC Conversation Analyzer Tests
# ====================================================================

class TestNPCData(unittest.TestCase):

    def test_default_values(self):
        npc = NPCData()
        self.assertEqual(npc.name, "")
        self.assertEqual(npc.keywords, [])
        self.assertFalse(npc.has_greet)
        self.assertFalse(npc.has_shop_module)

    def test_to_dict(self):
        npc = NPCData(name="TestNPC", file="test.xml")
        npc.keywords = ["hello", "bye"]
        npc.has_greet = True
        d = npc.to_dict()
        self.assertEqual(d["name"], "TestNPC")
        self.assertEqual(d["keywords"], ["hello", "bye"])
        self.assertTrue(d["has_greet"])


class TestNPCAnalyzerWithExamples(unittest.TestCase):
    """Test analyzer against the real example NPC files."""

    def setUp(self):
        self.npc_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "tfs03_input", "npc",
        )
        self.analyzer = NPCConversationAnalyzer(self.npc_dir)
        if os.path.isdir(self.npc_dir):
            self.analyzer.load_npcs()
        else:
            self.skipTest("Example NPC directory not found")

    def test_loads_two_npcs(self):
        self.assertEqual(len(self.analyzer.npcs), 2)

    def test_captain_npc_parsed(self):
        captain = next((n for n in self.analyzer.npcs if "Captain" in n.name), None)
        self.assertIsNotNone(captain)
        self.assertIn("travel", captain.keywords)
        self.assertIn("name", captain.keywords)
        self.assertTrue(captain.has_greet)

    def test_shopkeeper_npc_parsed(self):
        shop = next((n for n in self.analyzer.npcs if "Shopkeeper" in n.name), None)
        self.assertIsNotNone(shop)
        self.assertTrue(shop.has_shop_module)
        self.assertIn("ShopModule", shop.modules)
        self.assertGreater(len(shop.shop_buyable), 0)
        self.assertGreater(len(shop.shop_sellable), 0)

    def test_shop_items_parsed(self):
        shop = next((n for n in self.analyzer.npcs if "Shopkeeper" in n.name), None)
        self.assertIsNotNone(shop)
        # Should have sword and spear in buyable
        names = [item["name"] for item in shop.shop_buyable]
        self.assertIn("sword", names)
        self.assertIn("spear", names)

    def test_captain_keywords_from_lua(self):
        captain = next((n for n in self.analyzer.npcs if "Captain" in n.name), None)
        self.assertIsNotNone(captain)
        self.assertIn("travel", captain.keywords)

    def test_captain_responses(self):
        captain = next((n for n in self.analyzer.npcs if "Captain" in n.name), None)
        self.assertIsNotNone(captain)
        # Should have responses for keywords
        self.assertIn("name", captain.responses)

    def test_shopkeeper_keywords_from_lua(self):
        shop = next((n for n in self.analyzer.npcs if "Shopkeeper" in n.name), None)
        self.assertIsNotNone(shop)
        self.assertIn("balance", shop.keywords)
        self.assertIn("level", shop.keywords)
        self.assertIn("help", shop.keywords)

    def test_analyze_returns_all_sections(self):
        report = self.analyzer.analyze()
        self.assertIn("total_npcs", report)
        self.assertIn("npcs", report)
        self.assertIn("loops", report)
        self.assertIn("duplicate_keywords", report)
        self.assertIn("unreachable_responses", report)
        self.assertIn("greet_farewell", report)
        self.assertIn("shop_items", report)

    def test_format_report(self):
        text = self.analyzer.format_report()
        self.assertIn("NPC Conversation Analysis Report", text)
        self.assertIn("Captain", text)
        self.assertIn("Shopkeeper", text)

    def test_no_duplicate_keywords(self):
        dups = self.analyzer.detect_duplicate_keywords()
        for npc_file, info in dups.items():
            self.assertEqual(info["duplicates"], [])

    def test_greet_farewell_check(self):
        gf = self.analyzer.check_greet_farewell()
        for npc in self.analyzer.npcs:
            self.assertIn(npc.file, gf)
            self.assertTrue(gf[npc.file]["greet"])

    def test_visual_graph_output(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            graph_path = os.path.join(tmpdir, "graph.md")
            self.analyzer.generate_visual_graph(graph_path)
            self.assertTrue(os.path.exists(graph_path))
            with open(graph_path) as f:
                content = f.read()
            self.assertIn("mermaid", content)
            self.assertIn("graph TD", content)
            self.assertIn("Captain", content)


class TestNPCAnalyzerSynthetic(unittest.TestCase):
    """Test analyzer with synthetic NPC files."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _write_npc(self, xml_name, xml_content, lua_name=None, lua_content=None):
        xml_path = os.path.join(self.tmpdir, xml_name)
        with open(xml_path, "w", encoding="utf-8") as f:
            f.write(xml_content)
        if lua_name and lua_content:
            scripts_dir = os.path.join(self.tmpdir, "scripts")
            os.makedirs(scripts_dir, exist_ok=True)
            lua_path = os.path.join(scripts_dir, lua_name)
            with open(lua_path, "w", encoding="utf-8") as f:
                f.write(lua_content)

    def test_xml_parsing_greet_message(self):
        self._write_npc("test.xml", """<?xml version="1.0"?>
<npc name="TestNPC" script="test.lua">
  <parameter key="message_greet" value="Hello {trade}!"/>
</npc>
""")
        a = NPCConversationAnalyzer(self.tmpdir)
        a.load_npcs()
        self.assertEqual(len(a.npcs), 1)
        npc = a.npcs[0]
        self.assertEqual(npc.name, "TestNPC")
        self.assertTrue(npc.has_greet)
        self.assertIn("trade", npc.keywords)

    def test_xml_shop_items(self):
        self._write_npc("shop.xml", """<?xml version="1.0"?>
<npc name="ShopNPC" script="shop.lua">
  <parameter key="shop_buyable" value="100,item_a,50;200,item_b,100"/>
  <parameter key="shop_sellable" value="100,item_a,25"/>
</npc>
""")
        a = NPCConversationAnalyzer(self.tmpdir)
        a.load_npcs()
        npc = a.npcs[0]
        self.assertEqual(len(npc.shop_buyable), 2)
        self.assertEqual(len(npc.shop_sellable), 1)
        self.assertEqual(npc.shop_buyable[0]["name"], "item_a")

    def test_lua_keyword_parsing(self):
        self._write_npc("test.xml", """<?xml version="1.0"?>
<npc name="TalkNPC" script="talk.lua">
  <parameter key="message_greet" value="Hello!"/>
</npc>
""", "talk.lua", """
local keywordHandler = KeywordHandler:new()
local npcHandler = NpcHandler:new(keywordHandler)

function creatureSayCallback(cid, type, msg)
    if msgcontains(msg, "hello") then
        selfSay("Hi there!", cid)
    elseif msgcontains(msg, "quest") then
        selfSay("Go kill 10 rats.", cid)
    end
end
""")
        a = NPCConversationAnalyzer(self.tmpdir)
        a.load_npcs()
        npc = a.npcs[0]
        self.assertIn("hello", npc.keywords)
        self.assertIn("quest", npc.keywords)
        self.assertIn("hello", npc.responses)
        self.assertEqual(npc.responses["hello"], "Hi there!")
        self.assertEqual(npc.responses["quest"], "Go kill 10 rats.")

    def test_module_detection(self):
        self._write_npc("mod.xml", """<?xml version="1.0"?>
<npc name="ModNPC" script="mod.lua"/>
""", "mod.lua", """
local shopModule = ShopModule:new()
local focusModule = FocusModule:new()
""")
        a = NPCConversationAnalyzer(self.tmpdir)
        a.load_npcs()
        npc = a.npcs[0]
        self.assertTrue(npc.has_shop_module)
        self.assertTrue(npc.has_focus_module)
        self.assertIn("ShopModule", npc.modules)
        self.assertIn("FocusModule", npc.modules)

    def test_duplicate_keyword_detection(self):
        self._write_npc("dup.xml", """<?xml version="1.0"?>
<npc name="DupNPC" script="dup.lua"/>
""", "dup.lua", """
function creatureSayCallback(cid, type, msg)
    if msgcontains(msg, "hello") then
        selfSay("Hello!", cid)
    end
    if msgcontains(msg, "hello") then
        selfSay("Hello again!", cid)
    end
end
""")
        a = NPCConversationAnalyzer(self.tmpdir)
        a.load_npcs()
        dups = a.detect_duplicate_keywords()
        npc = a.npcs[0]
        self.assertIn("hello", dups[npc.file]["duplicates"])

    def test_empty_directory(self):
        empty_dir = os.path.join(self.tmpdir, "empty")
        os.makedirs(empty_dir)
        a = NPCConversationAnalyzer(empty_dir)
        a.load_npcs()
        self.assertEqual(len(a.npcs), 0)
        report = a.analyze()
        self.assertEqual(report["total_npcs"], 0)

    def test_invalid_xml_skipped(self):
        xml_path = os.path.join(self.tmpdir, "bad.xml")
        with open(xml_path, "w") as f:
            f.write("this is not xml")
        a = NPCConversationAnalyzer(self.tmpdir)
        a.load_npcs()
        self.assertEqual(len(a.npcs), 0)

    def test_non_npc_xml_skipped(self):
        xml_path = os.path.join(self.tmpdir, "other.xml")
        with open(xml_path, "w") as f:
            f.write('<?xml version="1.0"?><items><item id="1"/></items>')
        a = NPCConversationAnalyzer(self.tmpdir)
        a.load_npcs()
        self.assertEqual(len(a.npcs), 0)

    def test_nonexistent_directory(self):
        a = NPCConversationAnalyzer("/nonexistent/dir/xyz")
        a.load_npcs()
        self.assertEqual(len(a.npcs), 0)

    def test_validate_shop_items_with_items_xml(self):
        # Create items.xml
        items_xml_path = os.path.join(self.tmpdir, "items.xml")
        with open(items_xml_path, "w") as f:
            f.write('<?xml version="1.0"?><items><item id="100"/><item id="200"/></items>')

        self._write_npc("shop.xml", """<?xml version="1.0"?>
<npc name="ShopNPC" script="shop.lua">
  <parameter key="shop_buyable" value="100,sword,50;999,unknown_item,100"/>
</npc>
""")
        a = NPCConversationAnalyzer(self.tmpdir, items_xml=items_xml_path)
        a.load_npcs()
        validation = a.validate_shop_items()
        npc = a.npcs[0]
        invalid = validation[npc.file]["invalid_items"]
        self.assertEqual(len(invalid), 1)
        self.assertEqual(invalid[0]["id"], "999")

    def test_cycle_detection(self):
        npc = NPCData(name="CycleNPC", file="cycle.xml")
        npc.keywords = ["a", "b", "c"]
        npc.graph = {
            "greet": ["a"],
            "a": ["b"],
            "b": ["c"],
            "c": ["a"],  # cycle: a -> b -> c -> a
        }
        analyzer = NPCConversationAnalyzer(self.tmpdir)
        analyzer.npcs = [npc]
        loops = analyzer.detect_loops()
        self.assertTrue(loops["cycle.xml"]["has_loop"])

    def test_no_cycles(self):
        npc = NPCData(name="NoCycle", file="nocycle.xml")
        npc.keywords = ["a", "b"]
        npc.graph = {
            "greet": ["a", "b"],
            "a": [],
            "b": [],
        }
        analyzer = NPCConversationAnalyzer(self.tmpdir)
        analyzer.npcs = [npc]
        loops = analyzer.detect_loops()
        self.assertFalse(loops["nocycle.xml"]["has_loop"])

    def test_unreachable_detection(self):
        npc = NPCData(name="UnreachNPC", file="unreach.xml")
        npc.keywords = ["linked", "orphan"]
        npc.graph = {
            "greet": ["linked"],
            "linked": [],
            # "orphan" not reachable from greet
        }
        analyzer = NPCConversationAnalyzer(self.tmpdir)
        analyzer.npcs = [npc]
        result = analyzer.detect_unreachable_responses()
        self.assertIn("orphan", result["unreach.xml"]["unreachable"])
        self.assertNotIn("linked", result["unreach.xml"]["unreachable"])

    def test_farewell_detection(self):
        self._write_npc("fw.xml", """<?xml version="1.0"?>
<npc name="FarewellNPC" script="fw.lua">
  <parameter key="message_greet" value="Hello!"/>
  <parameter key="message_farewell" value="Goodbye!"/>
</npc>
""")
        a = NPCConversationAnalyzer(self.tmpdir)
        a.load_npcs()
        gf = a.check_greet_farewell()
        npc = a.npcs[0]
        self.assertTrue(gf[npc.file]["greet"])
        self.assertTrue(gf[npc.file]["farewell"])

    def test_format_report_renders(self):
        self._write_npc("rpt.xml", """<?xml version="1.0"?>
<npc name="ReportNPC" script="rpt.lua">
  <parameter key="message_greet" value="Hello!"/>
</npc>
""", "rpt.lua", """
function creatureSayCallback(cid, type, msg)
    if msgcontains(msg, "help") then
        selfSay("How can I help?", cid)
    end
end
""")
        a = NPCConversationAnalyzer(self.tmpdir)
        a.load_npcs()
        text = a.format_report()
        self.assertIn("ReportNPC", text)
        self.assertIn("help", text)
        self.assertIn("OK Greet handler", text)


# ====================================================================
# Integration: LuaTransformer + Explain
# ====================================================================

class TestLuaTransformerExplain(unittest.TestCase):

    def test_explain_entries_generated(self):
        from ttt.converters.lua_transformer import LuaTransformer
        from ttt.mappings.tfs03_functions import TFS03_TO_1X
        t = LuaTransformer(TFS03_TO_1X, "tfs03")
        explain = ExplainReport()
        t.explain = explain

        code = 'doPlayerAddItem(cid, 2160, 1)'
        t.transform(code, "test.lua")
        # Should have at least one explain entry
        self.assertGreater(len(explain.entries), 0)

    def test_explain_captures_stage(self):
        from ttt.converters.lua_transformer import LuaTransformer
        from ttt.mappings.tfs03_functions import TFS03_TO_1X
        t = LuaTransformer(TFS03_TO_1X, "tfs03")
        explain = ExplainReport()
        t.explain = explain

        code = 'doPlayerAddItem(cid, 2160, 1)'
        t.transform(code, "test.lua")
        stages = {e.stage for e in explain.entries}
        self.assertIn("function", stages)


class TestLuaTransformerRuleConfidence(unittest.TestCase):

    def test_rule_confidences_populated(self):
        from ttt.converters.lua_transformer import LuaTransformer
        from ttt.mappings.tfs03_functions import TFS03_TO_1X
        t = LuaTransformer(TFS03_TO_1X, "tfs03")
        code = 'doPlayerAddItem(cid, 2160, 1)'
        t.transform(code, "test.lua")
        self.assertGreater(len(t.rule_confidences), 0)
        for conf in t.rule_confidences:
            self.assertGreaterEqual(conf, 0.0)
            self.assertLessEqual(conf, 1.0)


if __name__ == "__main__":
    unittest.main()
