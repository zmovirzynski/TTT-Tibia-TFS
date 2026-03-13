"""Testes unitários do TTT."""

import os
import sys
import unittest
import tempfile
import shutil

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ttt.utils import split_lua_args
from ttt.converters.lua_transformer import LuaTransformer
from ttt.converters.xml_to_revscript import XmlToRevScriptConverter
from ttt.converters.npc_converter import NpcConverter
from ttt.diff_html import HtmlDiffGenerator, DiffEntry
from ttt.mappings.tfs03_functions import TFS03_TO_1X
from ttt.engine import ConversionEngine


class TestArgSplitter(unittest.TestCase):

    def test_simple_args(self):
        result = split_lua_args("cid, 2160, 1")
        self.assertEqual(result, ["cid", "2160", "1"])

    def test_nested_call(self):
        result = split_lua_args('cid, getItemIdByName("crystal coin"), 1')
        self.assertEqual(result, ["cid", 'getItemIdByName("crystal coin")', "1"])

    def test_string_with_comma(self):
        result = split_lua_args('cid, "Hello, World!", 1')
        self.assertEqual(result, ["cid", '"Hello, World!"', "1"])

    def test_table_arg(self):
        result = split_lua_args("cid, {x=100, y=200, z=7}")
        self.assertEqual(result, ["cid", "{x=100, y=200, z=7}"])

    def test_single_arg(self):
        result = split_lua_args("cid")
        self.assertEqual(result, ["cid"])

    def test_empty(self):
        result = split_lua_args("")
        self.assertEqual(result, [])


class TestLuaTransformer(unittest.TestCase):

    def setUp(self):
        self.transformer = LuaTransformer(TFS03_TO_1X, "tfs03")

    def test_signature_transform_onuse(self):
        code = "function onUse(cid, item, frompos, item2, topos)\n    return true\nend"
        result = self.transformer.transform(code)
        self.assertIn("function onUse(player, item, fromPosition, target, toPosition, isHotkey)", result)

    def test_signature_transform_onlogin(self):
        code = "function onLogin(cid)\n    return true\nend"
        result = self.transformer.transform(code)
        self.assertIn("function onLogin(player)", result)

    def test_signature_transform_onsay(self):
        code = "function onSay(cid, words, param)\n    return true\nend"
        result = self.transformer.transform(code)
        self.assertIn("function onSay(player, words, param)", result)

    def test_function_call_doPlayerSendTextMessage(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "Hello!")
    return true
end"""
        result = self.transformer.transform(code)
        self.assertIn('player:sendTextMessage(MESSAGE_STATUS_DEFAULT, "Hello!")', result)

    def test_function_call_getPlayerLevel(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    local level = getPlayerLevel(cid)
    return true
end"""
        result = self.transformer.transform(code)
        self.assertIn("player:getLevel()", result)

    def test_function_call_doPlayerAddItem(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    doPlayerAddItem(cid, 2160, 1)
    return true
end"""
        result = self.transformer.transform(code)
        self.assertIn("player:addItem(2160, 1)", result)

    def test_function_call_doTeleportThing(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    local dest = {x=1000, y=1000, z=7}
    doTeleportThing(cid, dest)
    return true
end"""
        result = self.transformer.transform(code)
        self.assertIn("player:teleportTo(dest)", result)

    def test_function_call_doSendMagicEffect(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    doSendMagicEffect(pos, CONST_ME_TELEPORT)
    return true
end"""
        result = self.transformer.transform(code)
        # 'pos' is recognized as a Position variable, no wrapping needed
        self.assertIn("pos:sendMagicEffect(CONST_ME_TELEPORT)", result)

    def test_static_call_broadcastMessage(self):
        code = """function onStartup()
    broadcastMessage("Hello!", MESSAGE_STATUS_WARNING)
    return true
end"""
        result = self.transformer.transform(code)
        self.assertIn('Game.broadcastMessage("Hello!", MESSAGE_STATUS_WARNING)', result)

    def test_static_call_createItem(self):
        code = 'doCreateItem(2160, 1, pos)'
        result = self.transformer.transform(code)
        self.assertIn("Game.createItem(2160, 1, pos)", result)

    def test_constant_replacement(self):
        code = "return TRUE"
        result = self.transformer.transform(code)
        self.assertIn("return true", result)

    def test_constant_false_replacement(self):
        code = "return FALSE"
        result = self.transformer.transform(code)
        self.assertIn("return false", result)

    def test_constant_lua_error(self):
        code = "return LUA_ERROR"
        result = self.transformer.transform(code)
        self.assertIn("return false", result)

    def test_constant_talktype(self):
        code = "doCreatureSay(cid, text, TALKTYPE_ORANGE_1)"
        result = self.transformer.transform(code)
        self.assertIn("TALKTYPE_MONSTER_SAY", result)

    def test_constant_return_value(self):
        code = "if result == RET_NOERROR then"
        result = self.transformer.transform(code)
        self.assertIn("RETURNVALUE_NOERROR", result)

    def test_position_transform(self):
        code = "local pos = {x = 100, y = 200, z = 7}"
        result = self.transformer.transform(code)
        self.assertIn("Position(100, 200, 7)", result)

    def test_variable_rename(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    local name = getCreatureName(cid)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, name)
    return true
end"""
        result = self.transformer.transform(code)
        # 'cid' should be renamed to 'player' in the body
        self.assertNotIn("getCreatureName(cid)", result)
        self.assertIn("player:getName()", result)

    def test_type_check_isPlayer(self):
        code = """function onStepIn(cid, item, position, fromPosition)
    if not isPlayer(cid) then
        return true
    end
end"""
        result = self.transformer.transform(code)
        # isPlayer should be converted to some form
        self.assertNotIn("isPlayer(cid)", result)

    def test_getPlayerStorageValue(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    local val = getPlayerStorageValue(cid, 50001)
    doPlayerSetStorageValue(cid, 50001, val + 1)
    return true
end"""
        result = self.transformer.transform(code)
        self.assertIn("player:getStorageValue(50001)", result)
        self.assertIn("player:setStorageValue(50001, val + 1)", result)

    def test_full_healing_potion_script(self):
        code = """function onUse(cid, item, frompos, item2, topos)
    if getPlayerLevel(cid) < 10 then
        doPlayerSendCancel(cid, "You need level 10 to use this item.")
        doSendMagicEffect(getCreaturePosition(cid), CONST_ME_POFF)
        return TRUE
    end

    local health = getCreatureHealth(cid)
    local maxHealth = getCreatureMaxHealth(cid)

    if health >= maxHealth then
        doPlayerSendTextMessage(cid, MESSAGE_STATUS_SMALL, "You are already at full health.")
        return TRUE
    end

    local healAmount = math.random(100, 200)
    doCreatureAddHealth(cid, healAmount)
    doSendMagicEffect(getCreaturePosition(cid), CONST_ME_MAGIC_BLUE)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "You healed " .. healAmount .. " health.")

    doRemoveItem(item.uid, 1)
    return TRUE
end"""
        result = self.transformer.transform(code)

        # Check key transformations
        self.assertIn("function onUse(player, item, fromPosition, target, toPosition, isHotkey)", result)
        self.assertIn("player:getLevel()", result)
        self.assertIn('player:sendCancelMessage("You need level 10 to use this item.")', result)
        self.assertIn("player:getHealth()", result)
        self.assertIn("player:getMaxHealth()", result)
        self.assertIn("player:addHealth(healAmount)", result)
        self.assertIn("return true", result)
        self.assertNotIn("return TRUE", result)
        self.assertNotIn("cid", result)


class TestXmlToRevScript(unittest.TestCase):

    def setUp(self):
        self.converter = XmlToRevScriptConverter()

    def test_parse_actions_xml(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<actions>
    <action itemid="2274" script="healing_potion.lua" />
    <action itemid="2275" script="teleport_scroll.lua" />
</actions>'''
        entries = self.converter._parse_xml_entries(xml, "action")
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["itemid"], "2274")
        self.assertEqual(entries[0]["script"], "healing_potion.lua")

    def test_parse_talkactions_xml(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<talkactions>
    <talkaction words="/bc" script="broadcast.lua" access="3" />
</talkactions>'''
        entries = self.converter._parse_xml_entries(xml, "talkaction")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["words"], "/bc")

    def test_parse_creaturescripts_xml(self):
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
<creaturescripts>
    <event type="login" name="PlayerLogin" script="login.lua" />
</creaturescripts>'''
        entries = self.converter._parse_xml_entries(xml, "event")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["type"], "login")

    def test_extract_function_body(self):
        code = """function onUse(player, item)
    player:addItem(2160, 1)
    return true
end"""
        body = self.converter._extract_function_body(code, "onUse")
        self.assertIsNotNone(body)
        self.assertIn("player:addItem(2160, 1)", body)
        self.assertIn("return true", body)

    def test_make_var_name(self):
        self.assertEqual(self.converter._make_var_name("healing_potion.lua"), "healing_potion")
        self.assertEqual(self.converter._make_var_name("TeleportScroll.lua"), "teleportScroll")
        self.assertEqual(self.converter._make_var_name("123test.lua"), "script_123test")


class TestConversionEngine(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.input_dir = os.path.join(self.test_dir, "input")
        self.output_dir = os.path.join(self.test_dir, "output")
        os.makedirs(self.input_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_validate_valid_conversion(self):
        engine = ConversionEngine("tfs03", "tfs1x", self.input_dir, self.output_dir)
        errors = engine.validate()
        self.assertEqual(len(errors), 0)

    def test_validate_invalid_conversion(self):
        engine = ConversionEngine("tfs1x", "tfs03", self.input_dir, self.output_dir)
        errors = engine.validate()
        self.assertGreater(len(errors), 0)

    def test_validate_missing_input(self):
        engine = ConversionEngine("tfs03", "tfs1x", "/nonexistent", self.output_dir)
        errors = engine.validate()
        self.assertGreater(len(errors), 0)

    def test_validate_same_directory(self):
        engine = ConversionEngine("tfs03", "tfs1x", self.input_dir, self.input_dir)
        errors = engine.validate()
        self.assertGreater(len(errors), 0)

    def test_simple_lua_conversion(self):
        # Create a simple input file
        lua_content = """function onUse(cid, item, frompos, item2, topos)
    doPlayerSendTextMessage(cid, MESSAGE_STATUS_DEFAULT, "Hello!")
    return TRUE
end"""
        os.makedirs(os.path.join(self.input_dir, "scripts"), exist_ok=True)
        with open(os.path.join(self.input_dir, "scripts", "test.lua"), "w") as f:
            f.write(lua_content)

        engine = ConversionEngine("tfs03", "tfs1x", self.input_dir, self.output_dir)
        stats = engine.run()

        # Check output exists
        out_file = os.path.join(self.output_dir, "scripts", "test.lua")
        self.assertTrue(os.path.exists(out_file))

        with open(out_file, "r") as f:
            result = f.read()

        self.assertIn("function onUse(player, item, fromPosition, target, toPosition, isHotkey)", result)
        self.assertIn('player:sendTextMessage(MESSAGE_STATUS_DEFAULT, "Hello!")', result)
        self.assertIn("return true", result)


class TestIntegration(unittest.TestCase):

    def test_convert_examples(self):
        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "tfs03_input"
        )

        if not os.path.exists(examples_dir):
            self.skipTest("Examples directory not found")

        output_dir = tempfile.mkdtemp()

        try:
            from ttt.utils import setup_logging
            setup_logging(verbose=False)

            engine = ConversionEngine("tfs03", "revscript", examples_dir, output_dir)
            stats = engine.run()

            # Verify no errors
            self.assertEqual(stats["errors"], 0, f"Conversion had errors: {stats}")

            # Check that RevScript files were generated
            scripts_dir = os.path.join(output_dir, "scripts")
            if os.path.exists(scripts_dir):
                lua_count = sum(
                    1 for root, _, files in os.walk(scripts_dir)
                    for f in files if f.endswith(".lua")
                )
                self.assertGreater(lua_count, 0, "No RevScript files generated")

        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


class TestNpcConverter(unittest.TestCase):

    def test_parse_npc_xml(self):
        converter = NpcConverter()
        xml_content = '''<?xml version="1.0"?>
<npc name="Captain" script="captain.lua" walkinterval="2000" floorchange="0">
    <health now="100" max="100"/>
    <look type="128" head="95" body="116" legs="114" feet="114" addons="3"/>
    <parameters>
        <parameter key="message_greet" value="Hello!"/>
    </parameters>
</npc>'''
        info = converter._parse_npc_xml(xml_content, "test.xml")
        self.assertIsNotNone(info)
        self.assertEqual(info["name"], "Captain")
        self.assertEqual(info["script"], "captain.lua")
        self.assertEqual(info["walkinterval"], "2000")
        self.assertEqual(info["look"]["type"], "128")
        self.assertEqual(info["health"]["max"], "100")
        self.assertEqual(info["parameters"]["message_greet"], "Hello!")

    def test_npc_header_generation(self):
        converter = NpcConverter()
        info = {
            "name": "Captain",
            "look": {"type": "128", "head": "95", "body": "116"},
            "health": {"now": "100", "max": "100"},
            "walkinterval": "2000",
        }
        header = converter._generate_npc_header(info)
        self.assertIn("-- NPC: Captain", header)
        self.assertIn("-- Look:", header)
        self.assertIn("-- Health: 100/100", header)
        self.assertIn("-- Walk interval: 2000", header)

    def test_npc_function_mappings(self):
        transformer = LuaTransformer(TFS03_TO_1X, "tfs03")

        # getNpcName() → Npc():getName()
        result = transformer.transform("local name = getNpcName()", "test.lua")
        self.assertIn("Npc():getName()", result)

        # getNpcPos() → Npc():getPosition()
        result = transformer.transform("local pos = getNpcPos()", "test.lua")
        self.assertIn("Npc():getPosition()", result)

        # selfMoveTo(pos) → Npc():move(pos)
        result = transformer.transform("selfMoveTo(pos)", "test.lua")
        self.assertIn("Npc():move(pos)", result)

        # selfTurn(dir) → Npc():turn(dir)
        result = transformer.transform("selfTurn(DIRECTION_SOUTH)", "test.lua")
        self.assertIn("Npc():turn(", result)

        # selfGetPosition() → Npc():getPosition()
        result = transformer.transform("local pos = selfGetPosition()", "test.lua")
        self.assertIn("Npc():getPosition()", result)

    def test_npc_script_conversion(self):
        transformer = LuaTransformer(TFS03_TO_1X, "tfs03")
        converter = NpcConverter(lua_transformer=transformer, dry_run=True)

        npc_code = '''function creatureSayCallback(cid, type, msg)
    if msgcontains(msg, "level") then
        local level = getPlayerLevel(cid)
        selfSay("You are level " .. level .. ".", cid)
    end
    return true
end'''

        output_dir = tempfile.mkdtemp()
        try:
            # Create temp files
            npc_dir = os.path.join(output_dir, "npc")
            scripts_dir = os.path.join(npc_dir, "scripts")
            os.makedirs(scripts_dir, exist_ok=True)

            xml_content = '''<?xml version="1.0"?>
<npc name="TestNpc" script="test.lua" walkinterval="2000">
    <health now="100" max="100"/>
    <look type="130"/>
</npc>'''
            xml_path = os.path.join(npc_dir, "testnpc.xml")
            with open(xml_path, "w") as f:
                f.write(xml_content)

            with open(os.path.join(scripts_dir, "test.lua"), "w") as f:
                f.write(npc_code)

            converter.convert_npc_folder(
                npc_dir=npc_dir,
                scripts_dir=scripts_dir,
                npc_xml_files=[xml_path],
                output_npc_dir=os.path.join(output_dir, "out_npc"),
            )

            # Check file reports
            reports = converter.pop_file_reports()
            self.assertTrue(len(reports) > 0, "Expected at least one file report")

            # Check the Lua report has transformations
            lua_reports = [r for r in reports if r.source_path.endswith(".lua")]
            self.assertTrue(len(lua_reports) > 0, "Expected a Lua file report")
            self.assertGreater(lua_reports[0].functions_converted, 0)

        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_npc_integration(self):
        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "tfs03_input"
        )

        npc_dir = os.path.join(examples_dir, "npc")
        if not os.path.exists(npc_dir):
            self.skipTest("NPC examples not found")

        output_dir = tempfile.mkdtemp()
        try:
            from ttt.utils import setup_logging
            setup_logging(verbose=False)

            engine = ConversionEngine("tfs03", "revscript", examples_dir, output_dir)
            stats = engine.run()

            self.assertEqual(stats["errors"], 0, f"Conversion had errors: {stats}")

            # Check NPC output exists
            out_npc = os.path.join(output_dir, "npc", "scripts")
            if os.path.exists(out_npc):
                lua_files = [f for f in os.listdir(out_npc) if f.endswith(".lua")]
                self.assertGreater(len(lua_files), 0, "No NPC scripts converted")

                # Verify content was transformed
                for lua_file in lua_files:
                    with open(os.path.join(out_npc, lua_file), "r") as f:
                        content = f.read()
                    # Should have NPC header
                    self.assertIn("-- NPC:", content)

        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


class TestHtmlDiff(unittest.TestCase):

    def test_diff_entry_creation(self):
        entry = DiffEntry(
            filename="healing.lua",
            original="local x = getPlayerLevel(cid)\n",
            converted="local x = player:getLevel()\n",
            file_type="action",
            functions_converted=1,
            total_changes=1,
        )
        self.assertEqual(entry.filename, "healing.lua")
        self.assertEqual(entry.functions_converted, 1)

    def test_diff_computation(self):
        gen = HtmlDiffGenerator("TFS 0.3", "RevScript", "/in", "/out")

        original = "line1\nline2\nline3\n"
        converted = "line1\nchanged\nline3\n"

        lines = gen._compute_diff_lines(original, converted)

        statuses = [l["status"] for l in lines]
        self.assertIn("equal", statuses)
        self.assertIn("change", statuses)
        self.assertEqual(statuses.count("equal"), 2)  # line1 and line3
        self.assertEqual(statuses.count("change"), 1)  # line2 → changed

    def test_diff_add_remove(self):
        gen = HtmlDiffGenerator("TFS 0.3", "RevScript", "/in", "/out")

        original = "aaa\nbbb\n"
        converted = "aaa\nccc\nbbb\n"

        lines = gen._compute_diff_lines(original, converted)
        statuses = [l["status"] for l in lines]
        self.assertIn("add", statuses)

    def test_html_generation(self):
        gen = HtmlDiffGenerator("TFS 0.3.6", "TFS 1.3+ (RevScript)", "/input", "/output")

        gen.add_entry(DiffEntry(
            filename="test_action.lua",
            original='function onUse(cid, item, frompos, item2, topos)\n'
                     '    doPlayerAddItem(cid, 2160, 1)\n'
                     '    return TRUE\n'
                     'end\n',
            converted='function onUse(player, item, fromPosition, target, toPosition, isHotkey)\n'
                      '    player:addItem(2160, 1)\n'
                      '    return true\n'
                      'end\n',
            file_type="action",
            confidence="HIGH",
            functions_converted=2,
            total_changes=3,
        ))

        gen.add_entry(DiffEntry(
            filename="unchanged.lua",
            original='print("hello")\n',
            converted='print("hello")\n',
            file_type="lua_transform",
        ))

        html = gen._build_html()

        # Check basic structure
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("TTT", html)
        self.assertIn("Visual Diff", html)
        self.assertIn("TFS 0.3.6", html)
        self.assertIn("RevScript", html)

        # Check file entries are present
        self.assertIn("test_action.lua", html)
        self.assertIn("unchanged.lua", html)

        # Check diff content — changed lines should appear
        self.assertIn("doPlayerAddItem", html)
        self.assertIn("player:addItem", html)

        # Check stats
        self.assertIn(">2<", html)  # total files
        self.assertIn(">1<", html)  # files changed

        # Check filter buttons
        self.assertIn("filterFiles", html)
        self.assertIn("Changed only", html)

    def test_html_generation_to_file(self):
        gen = HtmlDiffGenerator("TFS 0.3", "TFS 1.x", "/in", "/out")
        gen.add_entry(DiffEntry(
            filename="script.lua",
            original="getPlayerLevel(cid)\n",
            converted="player:getLevel()\n",
        ))

        output_dir = tempfile.mkdtemp(prefix="ttt_diff_test_")
        try:
            html_path = os.path.join(output_dir, "diff.html")
            result = gen.generate(html_path)

            self.assertTrue(os.path.isfile(html_path))
            with open(html_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("<!DOCTYPE html>", content)
            self.assertIn("script.lua", content)
            self.assertEqual(result, content)
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)

    def test_word_level_diff(self):
        gen = HtmlDiffGenerator("TFS 0.3", "TFS 1.x", "/in", "/out")

        left_html, right_html = gen._highlight_word_diff(
            "doPlayerAddItem(cid, 2160, 1)",
            "player:addItem(2160, 1)"
        )

        # Should have word-del and word-add spans
        self.assertIn("word-del", left_html)
        self.assertIn("word-add", right_html)

    def test_html_diff_integration(self):
        examples_dir = os.path.join(os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))), "examples", "tfs03_input")

        if not os.path.isdir(examples_dir):
            self.skipTest("Example files not found")

        output_dir = tempfile.mkdtemp(prefix="ttt_hdiff_int_")
        try:
            engine = ConversionEngine(
                "tfs03", "revscript", examples_dir, output_dir,
                html_diff=True,
            )
            stats = engine.run()

            html_path = os.path.join(output_dir, "conversion_diff.html")
            self.assertTrue(os.path.isfile(html_path),
                            "conversion_diff.html was not generated")

            with open(html_path, "r", encoding="utf-8") as f:
                html = f.read()
            self.assertIn("<!DOCTYPE html>", html)
            self.assertIn("Visual Diff", html)
            # Should contain file entries
            self.assertIn("file-card", html)
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main(verbosity=2)
