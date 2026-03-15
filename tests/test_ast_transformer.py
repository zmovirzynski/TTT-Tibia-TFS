"""Tests for AST-based Lua transformer components."""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from luaparser.astnodes import Name, Index, String, Call
    from ttt.converters.ast_utils import get_function_name, get_base_name, get_wrapper_class
    LUAPARSER_AVAILABLE = True
except ImportError:
    LUAPARSER_AVAILABLE = False


@unittest.skipUnless(LUAPARSER_AVAILABLE, "luaparser not installed")
class TestAstUtils(unittest.TestCase):

    def test_get_function_name_simple(self):
        node = Name("doPlayerAddItem")
        self.assertEqual(get_function_name(node), "doPlayerAddItem")

    def test_get_function_name_index(self):
        # Represents Game["createItem"]
        node = Index(value=Name("Game"), idx=String(b"createItem", "createItem"))
        self.assertEqual(get_function_name(node), "Game.createItem")

    def test_get_function_name_none_for_complex(self):
        # Call node as func — can't extract name
        node = Call(func=Name("f"), args=[])
        self.assertIsNone(get_function_name(node))

    def test_get_base_name_simple(self):
        self.assertEqual(get_base_name(Name("foo")), "foo")

    def test_get_base_name_nested_index(self):
        inner = Index(value=Name("a"), idx=String(b"b", "b"))
        self.assertEqual(get_base_name(inner), "a")

    def test_get_base_name_none(self):
        self.assertIsNone(get_base_name(String(b"x", "x")))

    def test_get_wrapper_class_known(self):
        self.assertEqual(get_wrapper_class("player"), "Player")
        self.assertEqual(get_wrapper_class("creature"), "Creature")
        self.assertEqual(get_wrapper_class("monster"), "Monster")
        self.assertEqual(get_wrapper_class("npc"), "Npc")
        self.assertEqual(get_wrapper_class("item"), "Item")
        self.assertEqual(get_wrapper_class("tile"), "Tile")
        self.assertEqual(get_wrapper_class("position"), "Position")

    def test_get_wrapper_class_fallback(self):
        self.assertEqual(get_wrapper_class("unknown_type"), "Creature")

    def test_get_wrapper_class_none(self):
        # var_type=None should not crash; returns fallback
        self.assertEqual(get_wrapper_class(None), "Creature")


@unittest.skipUnless(LUAPARSER_AVAILABLE, "luaparser not installed")
class TestScopeAnalyzer(unittest.TestCase):

    def _analyze(self, code: str):
        from luaparser import ast as luaast
        from ttt.converters.scope_analyzer import ScopeAnalyzer
        from ttt.mappings.signatures import SIGNATURE_MAP
        tree = luaast.parse(code)
        analyzer = ScopeAnalyzer(SIGNATURE_MAP)
        return analyzer.analyze(tree)

    def test_param_type_player_from_signature(self):
        code = "function onLogin(cid)\n    return true\nend"
        info = self._analyze(code)
        # cid in onLogin should be typed as 'player'
        scopes = dict(info.function_scopes)
        self.assertIn("onLogin", scopes)
        var = scopes["onLogin"].lookup("cid")
        self.assertIsNotNone(var)
        self.assertEqual(var.var_type, "player")

    def test_local_var_type_from_function_call(self):
        code = (
            "function onLogin(cid)\n"
            "    local target = getCreatureByName('Foo')\n"
            "    return true\nend"
        )
        info = self._analyze(code)
        scopes = dict(info.function_scopes)
        var = scopes["onLogin"].lookup("target")
        self.assertIsNotNone(var)
        self.assertEqual(var.var_type, "creature")

    def test_is_param_flag(self):
        code = "function onLogin(cid)\n    return true\nend"
        info = self._analyze(code)
        scopes = dict(info.function_scopes)
        var = scopes["onLogin"].lookup("cid")
        self.assertTrue(var.is_param)

    def test_local_var_is_not_param(self):
        code = (
            "function onLogin(cid)\n"
            "    local x = 1\n"
            "    return true\nend"
        )
        info = self._analyze(code)
        scopes = dict(info.function_scopes)
        var = scopes["onLogin"].lookup("x")
        self.assertIsNotNone(var)
        self.assertFalse(var.is_param)


    def test_anonymous_function_param_typed(self):
        """onUse = function(cid, item, ...) end — anonymous function via assignment."""
        code = (
            "onUse = function(cid, item, frompos, item2, topos)\n"
            "    return true\nend"
        )
        info = self._analyze(code)
        # The anonymous function should be associated with 'onUse'
        names = [name for name, _ in info.function_scopes]
        self.assertIn("onUse", names)
        scope = dict(info.function_scopes)["onUse"]
        var = scope.lookup("cid")
        self.assertIsNotNone(var)
        self.assertEqual(var.var_type, "player")

    def test_local_function_param_typed(self):
        """local function handler(cid) end — local function declaration."""
        code = "local function onLogin(cid)\n    return true\nend"
        info = self._analyze(code)
        names = [name for name, _ in info.function_scopes]
        self.assertIn("onLogin", names)
        scope = dict(info.function_scopes)["onLogin"]
        var = scope.lookup("cid")
        self.assertIsNotNone(var)
        self.assertEqual(var.var_type, "player")


if __name__ == "__main__":
    unittest.main()

