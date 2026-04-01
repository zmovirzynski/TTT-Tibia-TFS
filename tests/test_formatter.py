"""Unit tests for TTT Formatter (Phase 6)."""

import json
import os
import tempfile
import unittest

from ttt.formatter import (
    LuaFormatConfig,
    LuaFormatter,
    format_report_text,
)


class TestLuaFormatterCode(unittest.TestCase):
    def test_formats_indentation_and_operators(self):
        code = """function onUse(player,item)\nif player:getLevel()>=10 then\nplayer:addItem(2160,1)\nreturn true\nend\nend\n"""
        formatter = LuaFormatter(LuaFormatConfig())
        out = formatter.format_code(code)

        self.assertIn("function onUse(player,item)", out)
        self.assertIn("if player:getLevel() >= 10 then", out)
        self.assertIn("    player:addItem(2160,1)", out)
        self.assertIn("    return true", out)

    def test_tabs_indentation(self):
        code = """function onLogin(player)\nif true then\nprint('x')\nend\nend\n"""
        cfg = LuaFormatConfig(indent_style="tabs")
        out = LuaFormatter(cfg).format_code(code)
        self.assertIn("\tprint('x')", out)

    def test_adds_blank_line_between_functions(self):
        code = """function a()\n    return true\nend\nfunction b()\n    return true\nend\n"""
        cfg = LuaFormatConfig(blank_lines_between_functions=1)
        out = LuaFormatter(cfg).format_code(code)
        self.assertIn("end\n\nfunction b()", out)

    def test_aligns_table_fields_and_adds_trailing_commas(self):
        code = """local config = {\nname='Potion'\nid=7618\nprice=100\n}\n"""
        out = LuaFormatter(LuaFormatConfig()).format_code(code)

        self.assertIn("name  = 'Potion',", out)
        self.assertIn("id    = 7618,", out)
        self.assertIn("price = 100,", out)

    def test_trims_trailing_whitespace(self):
        code = "function x()    \n    return true    \nend    \n"
        out = LuaFormatter(LuaFormatConfig()).format_code(code)
        self.assertNotIn("    \n", out)


class TestLuaFormatterIO(unittest.TestCase):
    def test_check_mode_does_not_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "test.lua")
            with open(path, "w", encoding="utf-8") as f:
                f.write("function x()\nprint('a')\nend\n")

            fmt = LuaFormatter(LuaFormatConfig())
            result = fmt.format_file(path, check=True)

            self.assertTrue(result.changed)
            with open(path, "r", encoding="utf-8") as f:
                persisted = f.read()
            self.assertEqual(persisted, "function x()\nprint('a')\nend\n")

    def test_format_directory_returns_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.lua")
            b = os.path.join(tmp, "b.lua")

            with open(a, "w", encoding="utf-8") as f:
                f.write("function a()\nprint('a')\nend\n")
            with open(b, "w", encoding="utf-8") as f:
                f.write("function b()\n    return true\nend\n")

            report = LuaFormatter(LuaFormatConfig()).format_directory(tmp, check=True)
            self.assertEqual(report.files_scanned, 2)
            self.assertEqual(report.files_changed, 1)

            text = format_report_text(report, base_dir=tmp)
            self.assertIn("TTT Formatter Report", text)
            self.assertIn("Summary:", text)


class TestFormatterConfig(unittest.TestCase):
    def test_load_and_find_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = os.path.join(tmp, "a", "b")
            os.makedirs(nested, exist_ok=True)
            cfg_path = os.path.join(tmp, ".tttformat.json")
            with open(cfg_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "indentStyle": "tabs",
                        "indentSize": 2,
                        "spaceAroundOperators": False,
                    },
                    f,
                )

            found = LuaFormatConfig.find_config(nested)
            self.assertEqual(found, cfg_path)

            cfg = LuaFormatConfig.load(found)
            self.assertEqual(cfg.indent_style, "tabs")
            self.assertEqual(cfg.indent_size, 2)
            self.assertFalse(cfg.space_around_operators)


if __name__ == "__main__":
    unittest.main(verbosity=2)
