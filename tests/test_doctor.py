"""
Tests for TTT Server Doctor (Phase 3B).

Covers: health_check (6 checks), xml_validator (3 checks), engine, reporters.
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
# Health Check: Syntax Errors
# ===================================================================

class TestSyntaxCheck(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_missing_end(self):
        _make_tree(self.tmpdir, {
            "scripts/broken.lua": textwrap.dedent("""\
                function onUse(cid)
                    if true then
                        return true
            """),
        })
        from ttt.doctor.health_check import _check_lua_syntax
        issues = _check_lua_syntax(self.tmpdir)
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0].check_name, "syntax-error")
        self.assertIn("end", issues[0].message.lower())

    def test_extra_end(self):
        _make_tree(self.tmpdir, {
            "scripts/extra.lua": textwrap.dedent("""\
                function onUse(cid)
                    return true
                end
                end
            """),
        })
        from ttt.doctor.health_check import _check_lua_syntax
        issues = _check_lua_syntax(self.tmpdir)
        self.assertGreaterEqual(len(issues), 1)
        self.assertIn("extra", issues[0].message.lower())

    def test_unbalanced_parens(self):
        _make_tree(self.tmpdir, {
            "scripts/parens.lua": textwrap.dedent("""\
                function onUse(cid
                    return true
                end
            """),
        })
        from ttt.doctor.health_check import _check_lua_syntax
        issues = _check_lua_syntax(self.tmpdir)
        paren_issues = [i for i in issues if "parenthes" in i.message.lower()]
        self.assertGreaterEqual(len(paren_issues), 1)

    def test_valid_syntax(self):
        _make_tree(self.tmpdir, {
            "scripts/good.lua": textwrap.dedent("""\
                function onUse(cid)
                    if true then
                        return true
                    end
                end
            """),
        })
        from ttt.doctor.health_check import _check_lua_syntax
        issues = _check_lua_syntax(self.tmpdir)
        self.assertEqual(len(issues), 0)

    def test_comments_and_strings_ignored(self):
        """Block openers in comments/strings should not count."""
        _make_tree(self.tmpdir, {
            "scripts/okay.lua": textwrap.dedent("""\
                function onUse(cid)
                    -- if true then
                    local s = "function for end"
                    return true
                end
            """),
        })
        from ttt.doctor.health_check import _check_lua_syntax
        issues = _check_lua_syntax(self.tmpdir)
        self.assertEqual(len(issues), 0)


# ===================================================================
# Health Check: Broken XML References
# ===================================================================

class TestBrokenXmlRefs(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_missing_script(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": '<actions><action itemid="1" script="missing.lua"/></actions>',
        })
        from ttt.doctor.health_check import _check_broken_xml_refs
        issues = _check_broken_xml_refs(self.tmpdir)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].check_name, "broken-xml-ref")
        self.assertIn("missing.lua", issues[0].message)

    def test_existing_script(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": '<actions><action itemid="1" script="good.lua"/></actions>',
            "actions/scripts/good.lua": "-- ok",
        })
        from ttt.doctor.health_check import _check_broken_xml_refs
        issues = _check_broken_xml_refs(self.tmpdir)
        self.assertEqual(len(issues), 0)


# ===================================================================
# Health Check: Conflicting IDs
# ===================================================================

class TestConflictingIds(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_duplicate_action_itemid(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <actions>
                    <action itemid="2274" script="a.lua"/>
                    <action itemid="2274" script="b.lua"/>
                </actions>
            """),
        })
        from ttt.doctor.health_check import _check_conflicting_ids
        issues = _check_conflicting_ids(self.tmpdir)
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0].check_name, "conflicting-id")

    def test_unique_ids_no_conflict(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <actions>
                    <action itemid="2274" script="a.lua"/>
                    <action itemid="2275" script="b.lua"/>
                </actions>
            """),
        })
        from ttt.doctor.health_check import _check_conflicting_ids
        issues = _check_conflicting_ids(self.tmpdir)
        self.assertEqual(len(issues), 0)

    def test_duplicate_movement_itemid(self):
        _make_tree(self.tmpdir, {
            "movements/movements.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <movements>
                    <movevent itemid="1945" event="StepIn" script="a.lua"/>
                    <movevent itemid="1945" event="StepIn" script="b.lua"/>
                </movements>
            """),
        })
        from ttt.doctor.health_check import _check_conflicting_ids
        issues = _check_conflicting_ids(self.tmpdir)
        self.assertGreaterEqual(len(issues), 1)


# ===================================================================
# Health Check: Duplicate Events
# ===================================================================

class TestDuplicateEvents(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_duplicate_talkaction_keyword(self):
        _make_tree(self.tmpdir, {
            "talkactions/talkactions.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <talkactions>
                    <talkaction words="!info" script="info1.lua"/>
                    <talkaction words="!info" script="info2.lua"/>
                </talkactions>
            """),
        })
        from ttt.doctor.health_check import _check_duplicate_events
        issues = _check_duplicate_events(self.tmpdir)
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0].check_name, "duplicate-event")
        self.assertIn("!info", issues[0].message)

    def test_duplicate_creature_event(self):
        _make_tree(self.tmpdir, {
            "creaturescripts/creaturescripts.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <creaturescripts>
                    <event type="login" name="PlayerLogin" script="login1.lua"/>
                    <event type="login" name="PlayerLogin" script="login2.lua"/>
                </creaturescripts>
            """),
        })
        from ttt.doctor.health_check import _check_duplicate_events
        issues = _check_duplicate_events(self.tmpdir)
        self.assertGreaterEqual(len(issues), 1)

    def test_no_duplicates(self):
        _make_tree(self.tmpdir, {
            "talkactions/talkactions.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <talkactions>
                    <talkaction words="!info" script="info.lua"/>
                    <talkaction words="!help" script="help.lua"/>
                </talkactions>
            """),
        })
        from ttt.doctor.health_check import _check_duplicate_events
        issues = _check_duplicate_events(self.tmpdir)
        self.assertEqual(len(issues), 0)


# ===================================================================
# Health Check: NPC Keyword Duplicates
# ===================================================================

class TestNpcKeywords(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_duplicate_npc_keyword(self):
        _make_tree(self.tmpdir, {
            "npc/scripts/trader.lua": textwrap.dedent("""\
                function creatureSayCallback(cid, type, msg)
                    if msgcontains(msg, "trade") then
                        selfSay("Let's trade!", cid)
                    end
                    if msgcontains(msg, "trade") then
                        selfSay("What do you want?", cid)
                    end
                end
            """),
        })
        from ttt.doctor.health_check import _check_npc_keywords
        issues = _check_npc_keywords(self.tmpdir)
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0].check_name, "npc-duplicate-keyword")
        self.assertIn("trade", issues[0].message)

    def test_unique_keywords(self):
        _make_tree(self.tmpdir, {
            "npc/scripts/trader.lua": textwrap.dedent("""\
                function creatureSayCallback(cid, type, msg)
                    if msgcontains(msg, "trade") then
                        selfSay("Let's trade!", cid)
                    end
                    if msgcontains(msg, "name") then
                        selfSay("I am the trader.", cid)
                    end
                end
            """),
        })
        from ttt.doctor.health_check import _check_npc_keywords
        issues = _check_npc_keywords(self.tmpdir)
        self.assertEqual(len(issues), 0)


# ===================================================================
# Health Check: Invalid Callback Signatures
# ===================================================================

class TestInvalidCallbacks(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_too_few_params(self):
        _make_tree(self.tmpdir, {
            "scripts/action.lua": textwrap.dedent("""\
                function onUse()
                    return true
                end
            """),
        })
        from ttt.doctor.health_check import _check_callback_signatures
        issues = _check_callback_signatures(self.tmpdir)
        self.assertGreaterEqual(len(issues), 1)
        self.assertEqual(issues[0].check_name, "invalid-callback")
        self.assertIn("onUse", issues[0].message)

    def test_valid_callback(self):
        _make_tree(self.tmpdir, {
            "scripts/action.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    return true
                end
            """),
        })
        from ttt.doctor.health_check import _check_callback_signatures
        issues = _check_callback_signatures(self.tmpdir)
        self.assertEqual(len(issues), 0)

    def test_oop_callback_valid(self):
        _make_tree(self.tmpdir, {
            "scripts/action.lua": textwrap.dedent("""\
                function onUse(player, item, fromPosition, target, toPosition, isHotkey)
                    return true
                end
            """),
        })
        from ttt.doctor.health_check import _check_callback_signatures
        issues = _check_callback_signatures(self.tmpdir)
        self.assertEqual(len(issues), 0)


# ===================================================================
# Health Check: run_health_checks integration
# ===================================================================

class TestRunHealthChecks(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_full_check_clean(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": '<actions><action itemid="1" script="a.lua"/></actions>',
            "actions/scripts/a.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    return true
                end
            """),
        })
        from ttt.doctor.health_check import run_health_checks
        report = run_health_checks(self.tmpdir)
        self.assertEqual(report.total_issues, 0)
        self.assertGreater(report.total_files_scanned, 0)

    def test_full_check_with_issues(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": '<actions><action itemid="1" script="missing.lua"/></actions>',
            "bad.lua": "function broken(\nif true then\nend\n",
        })
        from ttt.doctor.health_check import run_health_checks
        report = run_health_checks(self.tmpdir)
        self.assertGreater(report.total_issues, 0)
        self.assertGreater(len(report.errors), 0)

    def test_as_dict(self):
        _make_tree(self.tmpdir, {
            "test.lua": "function onUse() return true end",
        })
        from ttt.doctor.health_check import run_health_checks
        report = run_health_checks(self.tmpdir)
        d = report.as_dict()
        self.assertIn("issues", d)
        self.assertIn("total_issues", d)
        self.assertIn("total_errors", d)

    def test_sort_errors_first(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": '<actions><action itemid="1" script="missing.lua"/></actions>',
            "scripts/a.lua": "function onUse()\nreturn true\nend",
        })
        from ttt.doctor.health_check import run_health_checks
        report = run_health_checks(self.tmpdir)
        if len(report.issues) >= 2:
            # Errors should come before warnings
            sev_order = [i.severity for i in report.issues]
            error_indices = [i for i, s in enumerate(sev_order) if s == "error"]
            warning_indices = [i for i, s in enumerate(sev_order) if s == "warning"]
            if error_indices and warning_indices:
                self.assertLess(max(error_indices), min(warning_indices))


# ===================================================================
# XML Validator: Well-formed
# ===================================================================

class TestXmlWellformed(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_malformed_xml(self):
        _make_tree(self.tmpdir, {
            "broken.xml": "<actions><action><</actions>",
        })
        from ttt.doctor.xml_validator import validate_xml_files
        report = validate_xml_files(self.tmpdir)
        errors = [i for i in report.issues if i.check_name == "xml-malformed"]
        self.assertGreaterEqual(len(errors), 1)

    def test_valid_xml(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": '<actions><action itemid="1" script="a.lua"/></actions>',
            "actions/scripts/a.lua": "-- ok",
        })
        from ttt.doctor.xml_validator import validate_xml_files
        report = validate_xml_files(self.tmpdir)
        errors = [i for i in report.issues if i.check_name == "xml-malformed"]
        self.assertEqual(len(errors), 0)

    def test_file_count(self):
        _make_tree(self.tmpdir, {
            "a.xml": "<root/>",
            "b.xml": "<root/>",
            "c.xml": "<root/>",
        })
        from ttt.doctor.xml_validator import validate_xml_files
        report = validate_xml_files(self.tmpdir)
        self.assertEqual(report.total_files_scanned, 3)
        self.assertEqual(report.total_files_valid, 3)


# ===================================================================
# XML Validator: Required Attributes
# ===================================================================

class TestXmlRequiredAttrs(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_talkaction_missing_words(self):
        _make_tree(self.tmpdir, {
            "talkactions.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <talkactions>
                    <talkaction script="test.lua"/>
                </talkactions>
            """),
        })
        from ttt.doctor.xml_validator import validate_xml_files
        report = validate_xml_files(self.tmpdir)
        attr_issues = [i for i in report.issues if i.check_name == "xml-missing-attr"]
        # Should flag missing 'words'
        has_words_warning = any("words" in i.message for i in attr_issues)
        self.assertTrue(has_words_warning)

    def test_action_with_all_attrs(self):
        _make_tree(self.tmpdir, {
            "actions.xml": textwrap.dedent("""\
                <?xml version="1.0"?>
                <actions>
                    <action itemid="2274" script="heal.lua"/>
                </actions>
            """),
            "scripts/heal.lua": "-- ok",
        })
        from ttt.doctor.xml_validator import validate_xml_files
        report = validate_xml_files(self.tmpdir)
        attr_issues = [i for i in report.issues
                       if i.check_name == "xml-missing-attr"
                       and "action" in i.message.lower()]
        # Should not flag action missing attrs (has both itemid and script)
        action_script_issues = [i for i in attr_issues if "script" in i.message]
        self.assertEqual(len(action_script_issues), 0)


# ===================================================================
# XML Validator: Script Paths
# ===================================================================

class TestXmlScriptPaths(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_missing_script_path(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": '<actions><action itemid="1" script="ghost.lua"/></actions>',
        })
        from ttt.doctor.xml_validator import validate_xml_files
        report = validate_xml_files(self.tmpdir)
        script_issues = [i for i in report.issues if i.check_name == "xml-missing-script"]
        self.assertGreaterEqual(len(script_issues), 1)
        self.assertIn("ghost.lua", script_issues[0].message)

    def test_existing_script_path(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": '<actions><action itemid="1" script="heal.lua"/></actions>',
            "actions/scripts/heal.lua": "-- ok",
        })
        from ttt.doctor.xml_validator import validate_xml_files
        report = validate_xml_files(self.tmpdir)
        script_issues = [i for i in report.issues if i.check_name == "xml-missing-script"]
        self.assertEqual(len(script_issues), 0)


# ===================================================================
# XML Validator: as_dict
# ===================================================================

class TestXmlValidatorDict(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_as_dict(self):
        _make_tree(self.tmpdir, {
            "test.xml": "<root/>",
        })
        from ttt.doctor.xml_validator import validate_xml_files
        report = validate_xml_files(self.tmpdir)
        d = report.as_dict()
        self.assertIn("issues", d)
        self.assertIn("total_files_scanned", d)
        self.assertIn("total_files_valid", d)
        self.assertIn("total_issues", d)


# ===================================================================
# Engine
# ===================================================================

class TestDoctorEngine(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_full_diagnosis(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": '<actions><action itemid="2274" script="heal.lua"/></actions>',
            "actions/scripts/heal.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    return true
                end
            """),
        })
        from ttt.doctor.engine import DoctorEngine
        engine = DoctorEngine()
        report = engine.diagnose(self.tmpdir)

        self.assertIsNotNone(report.health)
        self.assertIsNotNone(report.xml_validation)

    def test_only_health_check(self):
        _make_tree(self.tmpdir, {
            "scripts/a.lua": "function f() return true end",
        })
        from ttt.doctor.engine import DoctorEngine
        engine = DoctorEngine(enabled_modules=["health_check"])
        report = engine.diagnose(self.tmpdir)

        self.assertIsNotNone(report.health)
        self.assertIsNone(report.xml_validation)

    def test_only_xml_validator(self):
        _make_tree(self.tmpdir, {
            "test.xml": "<root/>",
        })
        from ttt.doctor.engine import DoctorEngine
        engine = DoctorEngine(enabled_modules=["xml_validator"])
        report = engine.diagnose(self.tmpdir)

        self.assertIsNone(report.health)
        self.assertIsNotNone(report.xml_validation)

    def test_as_dict(self):
        _make_tree(self.tmpdir, {
            "test.lua": "function f() return true end",
        })
        from ttt.doctor.engine import DoctorEngine
        engine = DoctorEngine()
        report = engine.diagnose(self.tmpdir)
        d = report.as_dict()
        self.assertIn("health_score", d)
        self.assertIn("health_rating", d)
        self.assertIn("total_issues", d)


# ===================================================================
# Health Score
# ===================================================================

class TestHealthScore(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_healthy_server(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": '<actions><action itemid="1" script="a.lua"/></actions>',
            "actions/scripts/a.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    return true
                end
            """),
        })
        from ttt.doctor.engine import DoctorEngine
        engine = DoctorEngine()
        report = engine.diagnose(self.tmpdir)
        self.assertEqual(report.health_rating, "HEALTHY")
        self.assertGreaterEqual(report.health_score, 90)

    def test_critical_server(self):
        _make_tree(self.tmpdir, {
            "actions/actions.xml": textwrap.dedent("""\
                <actions>
                    <action itemid="1" script="missing1.lua"/>
                    <action itemid="1" script="missing2.lua"/>
                    <action itemid="2" script="missing3.lua"/>
                    <action itemid="2" script="missing4.lua"/>
                </actions>
            """),
            "bad1.lua": "function broken(\nif then\nend\n",
            "bad2.lua": "function broken2(\nfor\nend\n",
        })
        from ttt.doctor.engine import DoctorEngine
        engine = DoctorEngine()
        report = engine.diagnose(self.tmpdir)
        self.assertEqual(report.health_rating, "CRITICAL")
        self.assertLess(report.health_score, 60)

    def test_empty_server(self):
        from ttt.doctor.engine import DoctorEngine
        engine = DoctorEngine()
        report = engine.diagnose(self.tmpdir)
        self.assertEqual(report.health_rating, "HEALTHY")
        self.assertEqual(report.health_score, 100)


# ===================================================================
# Reporters
# ===================================================================

class TestReporters(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        _make_tree(self.tmpdir, {
            "actions/actions.xml": textwrap.dedent("""\
                <actions>
                    <action itemid="1" script="missing.lua"/>
                    <action itemid="1" script="a.lua"/>
                </actions>
            """),
            "actions/scripts/a.lua": textwrap.dedent("""\
                function onUse(cid, item, frompos, item2, topos)
                    return true
                end
            """),
        })
        from ttt.doctor.engine import DoctorEngine
        engine = DoctorEngine()
        self.report = engine.diagnose(self.tmpdir)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_text_format(self):
        from ttt.doctor.engine import format_doctor_text
        text = format_doctor_text(self.report, no_color=True)
        self.assertIn("Health Score", text)
        self.assertIn("SUMMARY", text)

    def test_text_no_color(self):
        from ttt.doctor.engine import format_doctor_text
        text = format_doctor_text(self.report, no_color=True)
        self.assertNotIn("\033[", text)

    def test_json_format(self):
        from ttt.doctor.engine import format_doctor_json
        j = format_doctor_json(self.report)
        data = json.loads(j)
        self.assertIn("health_score", data)
        self.assertIn("health_rating", data)
        self.assertIn("health_check", data)
        self.assertIn("xml_validation", data)

    def test_html_format(self):
        from ttt.doctor.engine import format_doctor_html
        html = format_doctor_html(self.report)
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Health Report", html)
        self.assertIn("/100", html)


# ===================================================================
# Example Data (integration)
# ===================================================================

class TestExampleData(unittest.TestCase):
    """Test doctor against the real example data."""

    EXAMPLES_DIR = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "examples", "tfs03_input"
    )

    @unittest.skipUnless(
        os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    "examples", "tfs03_input")),
        "Example data not present"
    )
    def test_doctor_examples(self):
        from ttt.doctor.engine import DoctorEngine
        engine = DoctorEngine()
        report = engine.diagnose(self.EXAMPLES_DIR)

        self.assertIsNotNone(report.health)
        self.assertIsNotNone(report.xml_validation)
        # Example data should be healthy
        self.assertEqual(report.health_rating, "HEALTHY")
        self.assertEqual(report.total_errors, 0)

    @unittest.skipUnless(
        os.path.isdir(os.path.join(os.path.dirname(os.path.dirname(__file__)),
                                    "examples", "tfs03_input")),
        "Example data not present"
    )
    def test_xml_validation_examples(self):
        from ttt.doctor.xml_validator import validate_xml_files
        report = validate_xml_files(self.EXAMPLES_DIR)
        self.assertGreater(report.total_files_scanned, 0)
        # All example XMLs should be valid
        errors = [i for i in report.issues if i.check_name == "xml-malformed"]
        self.assertEqual(len(errors), 0)


if __name__ == "__main__":
    unittest.main()
