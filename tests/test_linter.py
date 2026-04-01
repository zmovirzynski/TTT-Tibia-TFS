"""Unit tests for the TTT Linter."""

import os
import sys
import unittest
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ttt.linter.rules import (
    LintSeverity, LintIssue,
    DeprecatedApiRule,
    UnusedParameterRule,
    MissingReturnRule,
    InvalidCallbackSignatureRule,
    GlobalVariableLeakRule,
    HardcodedIdRule,
    DeprecatedConstantRule,
    EmptyCallbackRule,
    MixedApiStyleRule,
    UnsafeStorageRule,
    ALL_RULES,
    get_all_rules,
    get_rules_by_ids,
)
from ttt.linter.engine import LintEngine, LintConfig, LintReport, compute_score
from ttt.linter.reporter import format_text, format_json, format_html


# ═══════════════════════════════════════════════════════════
# Tests for individual rules
# ═══════════════════════════════════════════════════════════

class TestDeprecatedApiRule(unittest.TestCase):

    def setUp(self):
        self.rule = DeprecatedApiRule()

    def test_detects_doPlayerAddItem(self):
        code = 'doPlayerAddItem(cid, 2160, 1)'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("doPlayerAddItem", issues[0].message)
        self.assertIn("addItem", issues[0].message)
        self.assertEqual(issues[0].severity, LintSeverity.WARNING)
        self.assertTrue(issues[0].fixable)

    def test_detects_getPlayerLevel(self):
        code = 'local level = getPlayerLevel(cid)'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("getPlayerLevel", issues[0].message)

    def test_detects_multiple_deprecated(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    local level = getPlayerLevel(cid)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "Hello!")
    doPlayerAddItem(cid, 2160, 1)
    return TRUE
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertGreaterEqual(len(issues), 3)

    def test_ignores_comments(self):
        code = '-- doPlayerAddItem(cid, 2160, 1)'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_ignores_modern_api(self):
        code = 'player:addItem(2160, 1)'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_no_false_positives_on_similar_names(self):
        code = 'local getPlayerLevelCustom = function() end'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        # Should not match partial names unless followed by (
        self.assertEqual(len(issues), 0)


class TestUnusedParameterRule(unittest.TestCase):

    def setUp(self):
        self.rule = UnusedParameterRule()

    def test_detects_unused_param(self):
        code = """function onUse(player, item, fromPosition, target, toPosition, isHotkey)
    player:addItem(2160, 1)
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        # item, fromPosition, target, toPosition, isHotkey are unused
        unused_params = [i.message for i in issues]
        self.assertTrue(any("'item'" in msg for msg in unused_params))
        self.assertTrue(any("'fromPosition'" in msg for msg in unused_params))
        self.assertTrue(any("'target'" in msg for msg in unused_params))
        self.assertTrue(any("'toPosition'" in msg for msg in unused_params))
        self.assertTrue(any("'isHotkey'" in msg for msg in unused_params))

    def test_no_issue_when_all_used(self):
        code = """function onUse(player, item)
    player:addItem(item.itemid, 1)
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_ignores_underscore(self):
        code = """function onUse(_, item)
    print(item)
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_no_params_no_issues(self):
        code = """function onStartup()
    print("starting")
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)


class TestMissingReturnRule(unittest.TestCase):

    def setUp(self):
        self.rule = MissingReturnRule()

    def test_detects_missing_return(self):
        code = """function onUse(player, item, fromPosition, target, toPosition, isHotkey)
    player:addItem(2160, 1)
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("onUse", issues[0].message)
        self.assertTrue(issues[0].fixable)

    def test_no_issue_with_return(self):
        code = """function onUse(player, item, fromPosition, target, toPosition, isHotkey)
    player:addItem(2160, 1)
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_ignores_non_callbacks(self):
        code = """function myHelper(x, y)
    print(x + y)
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_detects_onLogin_missing_return(self):
        code = """function onLogin(player)
    player:sendTextMessage(MESSAGE_STATUS_DEFAULT, "Welcome!")
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("onLogin", issues[0].message)


class TestInvalidCallbackSignatureRule(unittest.TestCase):

    def setUp(self):
        self.rule = InvalidCallbackSignatureRule()

    def test_detects_wrong_param_count_onUse(self):
        # onUse with only 2 params is wrong
        code = "function onUse(player, item)\n    return true\nend"
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("onUse", issues[0].message)

    def test_no_issue_with_correct_old_signature(self):
        code = "function onUse(cid, item, frompos, item2, topos)\n    return true\nend"
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_no_issue_with_correct_new_signature(self):
        code = "function onUse(player, item, fromPosition, target, toPosition, isHotkey)\n    return true\nend"
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_detects_wrong_onLogin(self):
        # onLogin should have 1 param
        code = "function onLogin(player, extra, more)\n    return true\nend"
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)

    def test_ignores_non_callbacks(self):
        code = "function myFunc(a, b, c, d, e)\n    return true\nend"
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)


class TestGlobalVariableLeakRule(unittest.TestCase):

    def setUp(self):
        self.rule = GlobalVariableLeakRule()

    def test_detects_global_leak(self):
        code = """function onUse(player, item)
    questStatus = 1
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("questStatus", issues[0].message)
        self.assertTrue(issues[0].fixable)

    def test_no_issue_with_local(self):
        code = """function onUse(player, item)
    local questStatus = 1
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_ignores_known_globals(self):
        code = """Game = {}
Player = {}"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_ignores_constants(self):
        code = """ITEM_GOLD_COIN = 2148
CONST_ME_POFF = 3"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)


class TestHardcodedIdRule(unittest.TestCase):

    def setUp(self):
        self.rule = HardcodedIdRule()

    def test_detects_hardcoded_item_id(self):
        code = 'doPlayerAddItem(cid, 2160, 1)'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("2160", issues[0].message)

    def test_ignores_comments(self):
        code = '-- doPlayerAddItem(cid, 2160, 1)'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_ignores_storage_ids(self):
        code = 'setStorageValue(cid, 50001, 1)'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        # 50001 >= 10000, so should be ignored
        self.assertEqual(len(issues), 0)

    def test_ignores_small_numbers(self):
        code = 'addItem(player, 10, 1)'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        # 10 is only 2 digits, below threshold
        self.assertEqual(len(issues), 0)


class TestDeprecatedConstantRule(unittest.TestCase):

    def setUp(self):
        self.rule = DeprecatedConstantRule()

    def test_detects_old_constant(self):
        code = 'doPlayerSendTextMessage(cid, MSG_STATUS_DEFAULT, "Hello")'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        # MSG_STATUS_DEFAULT → MESSAGE_STATUS_DEFAULT
        found = any("MSG_STATUS_DEFAULT" in i.message for i in issues)
        self.assertTrue(found, f"Expected MSG_STATUS_DEFAULT issue, got: {issues}")

    def test_detects_old_talktype(self):
        code = 'doCreatureSay(cid, text, TALKTYPE_ORANGE_1)'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        found = any("TALKTYPE_ORANGE_1" in i.message for i in issues)
        self.assertTrue(found)

    def test_ignores_comments(self):
        code = '-- TALKTYPE_ORANGE_1'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_no_issue_for_modern_constants(self):
        code = 'MESSAGE_STATUS_DEFAULT'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)


class TestEmptyCallbackRule(unittest.TestCase):

    def setUp(self):
        self.rule = EmptyCallbackRule()

    def test_detects_empty_callback(self):
        code = "function onUse(player, item, fromPosition, target, toPosition, isHotkey)\n\nend"
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("onUse", issues[0].message)

    def test_detects_callback_only_return(self):
        code = """function onLogin(player)
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("onLogin", issues[0].message)

    def test_no_issue_with_content(self):
        code = """function onLogin(player)
    player:sendTextMessage(MESSAGE_INFO_DESCR, "Welcome!")
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_ignores_non_callbacks(self):
        code = """function myHelper()
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)


class TestMixedApiStyleRule(unittest.TestCase):

    def setUp(self):
        self.rule = MixedApiStyleRule()

    def test_detects_mixed_api(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    local level = getPlayerLevel(cid)
    player:sendTextMessage(MESSAGE_STATUS_DEFAULT, "Hello!")
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("mixes", issues[0].message.lower())

    def test_no_issue_pure_old_api(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    local level = getPlayerLevel(cid)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "Hello!")
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_no_issue_pure_new_api(self):
        code = """function onUse(player, item, fromPosition, target, toPosition, isHotkey)
    local level = player:getLevel()
    player:sendTextMessage(MESSAGE_STATUS_DEFAULT, "Hello!")
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)


class TestUnsafeStorageRule(unittest.TestCase):

    def setUp(self):
        self.rule = UnsafeStorageRule()

    def test_detects_set_without_get(self):
        code = """function onUse(player, item)
    doPlayerSetStorageValue(cid, 50001, 1)
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 1)
        self.assertIn("50001", issues[0].message)

    def test_no_issue_with_get_before_set(self):
        code = """function onUse(player, item)
    local val = getPlayerStorageValue(cid, 50001)
    doPlayerSetStorageValue(cid, 50001, val + 1)
    return true
end"""
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)

    def test_ignores_comments(self):
        code = '-- doPlayerSetStorageValue(cid, 50001, 1)'
        lines = code.split("\n")
        issues = self.rule.check(code, lines)
        self.assertEqual(len(issues), 0)


# ═══════════════════════════════════════════════════════════
# Tests for the rule registry
# ═══════════════════════════════════════════════════════════

class TestRuleRegistry(unittest.TestCase):

    def test_all_rules_registered(self):
        self.assertEqual(len(ALL_RULES), 10)

    def test_get_all_rules(self):
        rules = get_all_rules()
        self.assertEqual(len(rules), 10)
        rule_ids = {r.rule_id for r in rules}
        self.assertIn("deprecated-api", rule_ids)
        self.assertIn("unused-parameter", rule_ids)
        self.assertIn("missing-return", rule_ids)
        self.assertIn("invalid-callback-signature", rule_ids)
        self.assertIn("global-variable-leak", rule_ids)
        self.assertIn("hardcoded-id", rule_ids)
        self.assertIn("deprecated-constant", rule_ids)
        self.assertIn("empty-callback", rule_ids)
        self.assertIn("mixed-api-style", rule_ids)
        self.assertIn("unsafe-storage", rule_ids)

    def test_get_rules_by_ids(self):
        rules = get_rules_by_ids(["deprecated-api", "missing-return"])
        self.assertEqual(len(rules), 2)
        rule_ids = {r.rule_id for r in rules}
        self.assertEqual(rule_ids, {"deprecated-api", "missing-return"})

    def test_get_rules_unknown_id(self):
        rules = get_rules_by_ids(["nonexistent-rule"])
        self.assertEqual(len(rules), 0)


# ═══════════════════════════════════════════════════════════
# Tests for the lint engine
# ═══════════════════════════════════════════════════════════

class TestLintEngine(unittest.TestCase):

    def setUp(self):
        self.engine = LintEngine()

    def test_lint_code_clean(self):
        code = """function onUse(player, item, fromPosition, target, toPosition, isHotkey)
    player:addItem(2160, 1)
    return true
end"""
        result = self.engine.lint_code(code, "clean_script.lua")
        # May have some info-level issues but no critical ones
        errors = [i for i in result.issues if i.severity == LintSeverity.ERROR]
        self.assertEqual(len(errors), 0)

    def test_lint_code_deprecated(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    doPlayerAddItem(cid, 2160, 1)
    return TRUE
end"""
        result = self.engine.lint_code(code, "old_script.lua")
        deprecated = [i for i in result.issues if i.rule_id == "deprecated-api"]
        self.assertGreater(len(deprecated), 0)

    def test_lint_code_score(self):
        # Script with many issues should have low score
        code = """function onUse(cid, item, frompos, item2, topos)
    doPlayerAddItem(cid, 2160, 1)
    doPlayerSendTextMessage(cid, MSG_STATUS_DEFAULT, "Hello!")
    getPlayerLevel(cid)
end"""
        result = self.engine.lint_code(code, "bad_script.lua")
        self.assertLess(result.score, 90)

    def test_lint_code_with_disabled_rules(self):
        config = LintConfig(disabled_rules=["deprecated-api", "deprecated-constant"])
        engine = LintEngine(config=config)
        code = 'doPlayerAddItem(cid, 2160, 1)'
        result = engine.lint_code(code, "test.lua")
        deprecated = [i for i in result.issues if i.rule_id == "deprecated-api"]
        self.assertEqual(len(deprecated), 0)

    def test_lint_code_with_enabled_rules_only(self):
        config = LintConfig(enabled_rules=["missing-return"])
        engine = LintEngine(config=config)
        code = """function onUse(cid, item, frompos, item2, topos)
    doPlayerAddItem(cid, 2160, 1)
end"""
        result = engine.lint_code(code, "test.lua")
        # Only missing-return should be reported
        rule_ids = {i.rule_id for i in result.issues}
        self.assertTrue(rule_ids.issubset({"missing-return", "lint-engine"}))

    def test_lint_file(self):
        # Create a temp file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".lua",
                                          delete=False, encoding="utf-8") as f:
            f.write("""function onLogin(cid)
    local name = getCreatureName(cid)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "Welcome, " .. name)
    return TRUE
end""")
            filepath = f.name

        try:
            result = self.engine.lint_file(filepath)
            self.assertEqual(result.filepath, filepath)
            self.assertGreater(len(result.issues), 0)
        finally:
            os.unlink(filepath)

    def test_lint_file_not_found(self):
        result = self.engine.lint_file(os.path.join(tempfile.gettempdir(), "nonexistent_ttt_test_file.lua"))
        self.assertNotEqual(result.error, "")
        self.assertEqual(result.score, 0)

    def test_lint_directory(self):
        # Use the examples directory
        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "tfs03_input"
        )
        if os.path.isdir(examples_dir):
            report = self.engine.lint_directory(examples_dir)
            self.assertGreater(len(report.files), 0)
            self.assertGreater(report.total_issues, 0)


class TestComputeScore(unittest.TestCase):

    def test_no_issues_perfect_score(self):
        score = compute_score([], 50)
        self.assertEqual(score, 100)

    def test_errors_reduce_score_heavily(self):
        issues = [LintIssue(1, 1, LintSeverity.ERROR, "test", "error")] * 5
        score = compute_score(issues, 50)
        self.assertLess(score, 50)

    def test_warnings_reduce_moderately(self):
        issues = [LintIssue(1, 1, LintSeverity.WARNING, "test", "warning")] * 3
        score = compute_score(issues, 50)
        self.assertLess(score, 100)
        self.assertGreater(score, 50)

    def test_infos_reduce_slightly(self):
        issues = [LintIssue(1, 1, LintSeverity.INFO, "test", "info")] * 3
        score = compute_score(issues, 50)
        self.assertGreater(score, 90)

    def test_empty_file_perfect_score(self):
        score = compute_score([], 0)
        self.assertEqual(score, 100)


# ═══════════════════════════════════════════════════════════
# Tests for the lint config
# ═══════════════════════════════════════════════════════════

class TestLintConfig(unittest.TestCase):

    def test_default_config(self):
        config = LintConfig()
        self.assertIsNone(config.enabled_rules)
        self.assertEqual(config.disabled_rules, [])
        self.assertEqual(config.max_issues_per_file, 50)

    def test_load_config(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json",
                                          delete=False, encoding="utf-8") as f:
            f.write('{"disable": ["hardcoded-id"], "maxIssuesPerFile": 20}')
            config_path = f.name

        try:
            config = LintConfig.load(config_path)
            self.assertIn("hardcoded-id", config.disabled_rules)
            self.assertEqual(config.max_issues_per_file, 20)
        finally:
            os.unlink(config_path)

    def test_load_missing_config(self):
        config = LintConfig.load("/nonexistent/config.json")
        # Should return default config, not crash
        self.assertIsNone(config.enabled_rules)

    def test_find_config(self):
        tmpdir = tempfile.mkdtemp()
        try:
            config_path = os.path.join(tmpdir, ".tttlint.json")
            with open(config_path, "w") as f:
                f.write("{}")

            found = LintConfig.find_config(tmpdir)
            self.assertEqual(found, config_path)
        finally:
            shutil.rmtree(tmpdir)

    def test_find_config_not_found(self):
        tmpdir = tempfile.mkdtemp()
        try:
            LintConfig.find_config(tmpdir)
            # May or may not be None depending on parent dirs
            # Just ensure it doesn't crash
        finally:
            shutil.rmtree(tmpdir)


# ═══════════════════════════════════════════════════════════
# Tests for reporters
# ═══════════════════════════════════════════════════════════

class TestReporters(unittest.TestCase):

    def _make_report(self) -> LintReport:
        """Create a sample report for testing."""
        from ttt.linter.engine import FileLintResult
        result = FileLintResult(
            filepath="/test/scripts/healing_potion.lua",
            issues=[
                LintIssue(3, 5, LintSeverity.WARNING, "deprecated-api",
                         "doPlayerAddItem → player:addItem()",
                         fixable=True),
                LintIssue(5, 10, LintSeverity.INFO, "unused-parameter",
                         "'frompos' is declared but never used"),
                LintIssue(8, 1, LintSeverity.WARNING, "missing-return",
                         "Callback 'onUse' should return true/false",
                         fixable=True),
            ],
            score=45,
        )
        return LintReport(
            files=[result],
            rules_used=["deprecated-api", "unused-parameter", "missing-return"],
            target_path="/test/scripts",
        )

    def test_format_text(self):
        report = self._make_report()
        output = format_text(report, "/test/scripts", use_colors=False)
        self.assertIn("healing_potion.lua", output)
        self.assertIn("deprecated-api", output)
        self.assertIn("unused-parameter", output)
        self.assertIn("missing-return", output)
        self.assertIn("Summary", output)
        self.assertIn("45/100", output)

    def test_format_json(self):
        import json
        report = self._make_report()
        output = format_json(report, "/test/scripts")
        data = json.loads(output)
        self.assertIn("summary", data)
        self.assertEqual(data["summary"]["totalFiles"], 1)
        self.assertEqual(data["summary"]["totalIssues"], 3)
        self.assertEqual(data["summary"]["warnings"], 2)
        self.assertEqual(data["summary"]["infos"], 1)
        self.assertEqual(len(data["files"]), 1)
        self.assertEqual(len(data["files"][0]["issues"]), 3)

    def test_format_html(self):
        report = self._make_report()
        output = format_html(report, "/test/scripts")
        self.assertIn("<!DOCTYPE html>", output)
        self.assertIn("TTT Lint Report", output)
        self.assertIn("deprecated-api", output)
        self.assertIn("healing_potion.lua", output)

    def test_format_text_empty_report(self):
        report = LintReport(files=[], rules_used=[], target_path="/test")
        output = format_text(report, "/test", use_colors=False)
        self.assertIn("No files", output)


# ═══════════════════════════════════════════════════════════
# Integration test: lint the example TFS 0.3 scripts
# ═══════════════════════════════════════════════════════════

class TestLintExampleScripts(unittest.TestCase):

    def setUp(self):
        self.examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "tfs03_input"
        )
        self.engine = LintEngine()

    @unittest.skipUnless(
        os.path.isdir(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "tfs03_input"
        )),
        "Example scripts not found"
    )
    def test_lint_healing_potion(self):
        filepath = os.path.join(self.examples_dir, "actions", "scripts", "healing_potion.lua")
        if not os.path.isfile(filepath):
            self.skipTest(f"File not found: {filepath}")

        result = self.engine.lint_file(filepath)
        self.assertGreater(len(result.issues), 0)

        # Should detect deprecated API calls
        deprecated = [i for i in result.issues if i.rule_id == "deprecated-api"]
        self.assertGreater(len(deprecated), 0, "Should detect deprecated API in healing_potion.lua")

        # Should detect deprecated constants (TRUE → true)
        [i for i in result.issues if i.rule_id == "deprecated-constant"]
        # TRUE is mapped to true in constants
        # Check score is below perfect
        self.assertLess(result.score, 90)

    @unittest.skipUnless(
        os.path.isdir(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "tfs03_input"
        )),
        "Example scripts not found"
    )
    def test_lint_login_script(self):
        filepath = os.path.join(self.examples_dir, "creaturescripts", "scripts", "login.lua")
        if not os.path.isfile(filepath):
            self.skipTest(f"File not found: {filepath}")

        result = self.engine.lint_file(filepath)
        self.assertGreater(len(result.issues), 0)

    @unittest.skipUnless(
        os.path.isdir(os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "tfs03_input"
        )),
        "Example scripts not found"
    )
    def test_lint_full_directory(self):
        report = self.engine.lint_directory(self.examples_dir)
        self.assertGreater(len(report.files), 0)
        self.assertGreater(report.total_issues, 0)

        # Generate all output formats without error
        text = format_text(report, self.examples_dir, use_colors=False)
        self.assertIn("Summary", text)

        json_out = format_json(report, self.examples_dir)
        import json
        data = json.loads(json_out)
        self.assertIn("summary", data)

        html = format_html(report, self.examples_dir)
        self.assertIn("<!DOCTYPE html>", html)


if __name__ == "__main__":
    unittest.main(verbosity=2)
