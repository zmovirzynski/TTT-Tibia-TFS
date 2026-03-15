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


if __name__ == "__main__":
    unittest.main()
