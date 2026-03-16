import os
import sys
import unittest
import tempfile
# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from ttt.generator import generate_script, TEMPLATE_TYPES

class TestScriptGenerator(unittest.TestCase):
    def test_generate_all_templates(self):
        for fmt in ("revscript", "tfs1x"):
            for script_type in TEMPLATE_TYPES:
                script, ext = generate_script(
                    script_type=script_type,
                    name="test_script",
                    output_format=fmt,
                    params=["param1", "param2"]
                )
                self.assertIsInstance(script, str)
                self.assertTrue(len(script) > 0)
                self.assertIn("test_script", script)
                self.assertIn("param1", script or "param2" in script)
                self.assertTrue(ext in ("lua", "xml"))

    def test_file_write(self):
        script, ext = generate_script(
            script_type="action",
            name="healing_potion",
            output_format="revscript",
            params=["cid", "item"]
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = os.path.join(tmpdir, f"healing_potion.{ext}")
            with open(out_path, "w", encoding="utf-8") as f:
                f.write(script)
            self.assertTrue(os.path.isfile(out_path))
            with open(out_path, "r", encoding="utf-8") as f:
                content = f.read()
            self.assertIn("healing_potion", content)
            self.assertIn("cid", content)

if __name__ == "__main__":
    unittest.main(verbosity=2)
