"""Tests for ttt.plugins — plugin loader, mapping packs, rule packs."""

import os
import tempfile
import textwrap

import pytest

from ttt.plugins.loader import (
    PluginLoader,
    PluginManifest,
    PluginError,
    load_mapping_pack,
    load_rule_pack,
    discover_plugins,
)


# ═══════════════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════════════


def _write_file(directory: str, name: str, content: str) -> str:
    path = os.path.join(directory, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(textwrap.dedent(content))
    return path


def _valid_mapping_toml() -> str:
    return """\
    [manifest]
    name = "test-mappings"
    version = "1.0.0"
    type = "mappings"

    [mappings.myOldFunc]
    method = "newFunc"
    obj_type = "player"
    obj_param = 0
    drop_params = [0]

    [mappings.anotherOldFunc]
    method = "anotherNew"
    obj_type = "creature"
    obj_param = 0
    drop_params = [0]
    """


def _valid_rule_py() -> str:
    return """\
    import re
    from typing import List
    from ttt.linter.rules import LintRule, LintIssue, LintSeverity

    class TestCheckRule(LintRule):
        rule_id = "test-check"
        description = "Test rule"
        severity = LintSeverity.INFO

        def check(self, code, lines, filename=""):
            return []

    RULES = {"test-check": TestCheckRule}
    """


# ═══════════════════════════════════════════════════════════════════════════
# load_mapping_pack
# ═══════════════════════════════════════════════════════════════════════════


class TestLoadMappingPack:
    """Tests for load_mapping_pack()."""

    def test_loads_valid_mapping_pack(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            path = _write_file(td, "mappings.toml", _valid_mapping_toml())
            result = load_mapping_pack(path)
            assert "myOldFunc" in result
            assert "anotherOldFunc" in result
            assert result["myOldFunc"]["method"] == "newFunc"

    def test_raises_on_missing_file(self):
        with pytest.raises(PluginError, match="not found"):
            load_mapping_pack("/nonexistent/path.toml")

    def test_raises_on_missing_manifest_name(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            path = _write_file(td, "bad.toml", """\
            [manifest]
            type = "mappings"

            [mappings.foo]
            method = "bar"
            """)
            with pytest.raises(PluginError, match="must include 'name'"):
                load_mapping_pack(path)

    def test_raises_on_wrong_type(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            path = _write_file(td, "bad.toml", """\
            [manifest]
            name = "test"
            type = "rules"

            [mappings.foo]
            method = "bar"
            """)
            with pytest.raises(PluginError, match="expected type 'mappings'"):
                load_mapping_pack(path)

    def test_raises_on_missing_method_key(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            path = _write_file(td, "bad.toml", """\
            [manifest]
            name = "test"
            type = "mappings"

            [mappings.foo]
            obj_type = "player"
            """)
            with pytest.raises(PluginError, match="missing required 'method'"):
                load_mapping_pack(path)

    def test_raises_on_invalid_toml(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            path = _write_file(td, "bad.toml", "this is not [valid toml !!!!")
            with pytest.raises(PluginError, match="Failed to parse"):
                load_mapping_pack(path)

    def test_loads_example_mapping_pack(self):
        """Load the bundled example mapping pack from examples/plugins/."""
        pytest.importorskip("tomllib")
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "plugins", "custom_mappings.toml",
        )
        if not os.path.exists(example_path):
            pytest.skip("Example mapping pack not found")
        result = load_mapping_pack(example_path)
        assert "getPlayerCustomPoints" in result
        assert len(result) >= 3


# ═══════════════════════════════════════════════════════════════════════════
# load_rule_pack
# ═══════════════════════════════════════════════════════════════════════════


class TestLoadRulePack:
    """Tests for load_rule_pack()."""

    def test_loads_valid_rule_pack(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_file(td, "rules.py", _valid_rule_py())
            result = load_rule_pack(path)
            assert "test-check" in result
            # Verify it's a proper LintRule subclass
            from ttt.linter.rules import LintRule
            assert issubclass(result["test-check"], LintRule)

    def test_raises_on_missing_file(self):
        with pytest.raises(PluginError, match="not found"):
            load_rule_pack("/nonexistent/rules.py")

    def test_raises_on_missing_rules_dict(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_file(td, "bad.py", """\
            # No RULES dict
            x = 42
            """)
            with pytest.raises(PluginError, match="must define a RULES dict"):
                load_rule_pack(path)

    def test_raises_on_non_lint_rule_class(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_file(td, "bad.py", """\
            class Fake:
                rule_id = "fake"

            RULES = {"fake": Fake}
            """)
            with pytest.raises(PluginError, match="must be a LintRule subclass"):
                load_rule_pack(path)

    def test_raises_on_rule_id_mismatch(self):
        with tempfile.TemporaryDirectory() as td:
            path = _write_file(td, "bad.py", """\
            from ttt.linter.rules import LintRule, LintIssue, LintSeverity

            class MyRule(LintRule):
                rule_id = "actual-id"
                description = "Test"
                severity = LintSeverity.INFO

                def check(self, code, lines, filename=""):
                    return []

            RULES = {"wrong-id": MyRule}
            """)
            with pytest.raises(PluginError, match="does not match dict key"):
                load_rule_pack(path)

    def test_loads_example_rule_pack(self):
        """Load the bundled example rule pack from examples/plugins/."""
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "plugins", "custom_rules.py",
        )
        if not os.path.exists(example_path):
            pytest.skip("Example rule pack not found")
        result = load_rule_pack(example_path)
        assert "custom-no-print" in result

    def test_example_rule_pack_detects_print(self):
        """Verify the example rule actually works."""
        example_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples", "plugins", "custom_rules.py",
        )
        if not os.path.exists(example_path):
            pytest.skip("Example rule pack not found")
        rules = load_rule_pack(example_path)
        rule = rules["custom-no-print"]()
        code = 'print("debug")\nlocal x = 1'
        issues = rule.check(code, code.splitlines())
        assert len(issues) == 1
        assert issues[0].rule_id == "custom-no-print"


# ═══════════════════════════════════════════════════════════════════════════
# discover_plugins
# ═══════════════════════════════════════════════════════════════════════════


class TestDiscoverPlugins:
    """Tests for discover_plugins()."""

    def test_discovers_mappings_and_rules(self):
        config = {
            "plugins": {
                "mappings": ["./custom/a.toml", "./custom/b.toml"],
                "rules": ["./custom/rules.py"],
            }
        }
        manifests = discover_plugins(config)
        assert len(manifests) == 3
        types = [m.type for m in manifests]
        assert types.count("mappings") == 2
        assert types.count("rules") == 1

    def test_returns_empty_when_no_plugins(self):
        assert discover_plugins({}) == []
        assert discover_plugins({"plugins": {}}) == []

    def test_manifest_paths_preserved(self):
        config = {"plugins": {"mappings": ["./my/pack.toml"]}}
        manifests = discover_plugins(config)
        assert manifests[0].path == "./my/pack.toml"


# ═══════════════════════════════════════════════════════════════════════════
# PluginLoader
# ═══════════════════════════════════════════════════════════════════════════


class TestPluginLoader:
    """Tests for PluginLoader high-level API."""

    def test_loads_mapping_and_rule_packs(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            m_path = _write_file(td, "mappings.toml", _valid_mapping_toml())
            r_path = _write_file(td, "rules.py", _valid_rule_py())

            config = {
                "plugins": {
                    "mappings": [m_path],
                    "rules": [r_path],
                }
            }

            loader = PluginLoader(config)
            loader.load_all()

            assert "myOldFunc" in loader.extra_mappings
            assert "test-check" in loader.extra_rules
            assert not loader.has_errors

    def test_collects_errors_for_missing_files(self):
        config = {
            "plugins": {
                "mappings": ["/nonexistent.toml"],
                "rules": ["/nonexistent.py"],
            }
        }
        loader = PluginLoader(config)
        loader.load_all()
        assert loader.has_errors
        assert len(loader.errors) == 2

    def test_detects_mapping_conflicts(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            p1 = _write_file(td, "pack1.toml", _valid_mapping_toml())
            p2 = _write_file(td, "pack2.toml", _valid_mapping_toml())

            config = {"plugins": {"mappings": [p1, p2]}}
            loader = PluginLoader(config)
            loader.load_all()

            # Both packs define the same keys → conflict errors
            assert loader.has_errors
            assert any("conflict" in e.lower() for e in loader.errors)

    def test_empty_config_does_nothing(self):
        loader = PluginLoader({})
        loader.load_all()
        assert not loader.has_errors
        assert len(loader.extra_mappings) == 0
        assert len(loader.extra_rules) == 0

    def test_manifests_populated_after_load(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            m_path = _write_file(td, "mappings.toml", _valid_mapping_toml())
            config = {"plugins": {"mappings": [m_path]}}

            loader = PluginLoader(config)
            loader.load_all()
            assert len(loader.manifests) == 1
            assert loader.manifests[0].type == "mappings"


# ═══════════════════════════════════════════════════════════════════════════
# PluginManifest
# ═══════════════════════════════════════════════════════════════════════════


class TestPluginManifest:
    """Tests for PluginManifest dataclass."""

    def test_defaults(self):
        m = PluginManifest()
        assert m.name == ""
        assert m.version == "0.0.0"
        assert m.type == ""
        assert m.description == ""
        assert m.path == ""

    def test_construction(self):
        m = PluginManifest(name="test", type="mappings", path="./a.toml")
        assert m.name == "test"
        assert m.type == "mappings"
