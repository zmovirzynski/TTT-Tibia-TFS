"""Tests for ttt.init — project scaffolding and project config loading."""

import os
import tempfile

import pytest

from ttt.init.scaffold import (
    InitResult,
    init_project,
    load_project_config,
    get_profile,
)


# ═══════════════════════════════════════════════════════════════════════════
# init_project
# ═══════════════════════════════════════════════════════════════════════════


class TestInitProject:
    """Tests for init_project() scaffold function."""

    def test_creates_project_toml(self):
        with tempfile.TemporaryDirectory() as td:
            result = init_project(td)
            assert result.created is True
            assert os.path.exists(result.path)
            assert result.path.endswith("ttt.project.toml")

    def test_default_content_has_project_section(self):
        with tempfile.TemporaryDirectory() as td:
            result = init_project(td)
            content = open(result.path, encoding="utf-8").read()
            assert "[project]" in content
            assert "[profiles.default]" in content
            assert "[profiles.quick]" in content
            assert "[profiles.full]" in content

    def test_uses_directory_name_as_default_project_name(self):
        with tempfile.TemporaryDirectory() as td:
            result = init_project(td)
            content = open(result.path, encoding="utf-8").read()
            basename = os.path.basename(td)
            assert f'name = "{basename}"' in content

    def test_custom_name_overrides_default(self):
        with tempfile.TemporaryDirectory() as td:
            result = init_project(td, name="my-cool-server")
            content = open(result.path, encoding="utf-8").read()
            assert 'name = "my-cool-server"' in content

    def test_custom_versions(self):
        with tempfile.TemporaryDirectory() as td:
            result = init_project(td, source_version="tfs04", target_version="tfs1x")
            content = open(result.path, encoding="utf-8").read()
            assert 'source_version = "tfs04"' in content
            assert 'target_version = "tfs1x"' in content

    def test_custom_paths(self):
        with tempfile.TemporaryDirectory() as td:
            result = init_project(td, input_dir="./src", output_dir="./dist")
            content = open(result.path, encoding="utf-8").read()
            assert 'input = "./src"' in content
            assert 'output = "./dist"' in content

    def test_refuses_overwrite_without_force(self):
        with tempfile.TemporaryDirectory() as td:
            init_project(td)
            result = init_project(td)
            assert result.created is False
            assert result.already_exists is True
            assert "already exists" in result.error

    def test_force_overwrites(self):
        with tempfile.TemporaryDirectory() as td:
            init_project(td, name="old-name")
            result = init_project(td, name="new-name", force=True)
            assert result.created is True
            content = open(result.path, encoding="utf-8").read()
            assert 'name = "new-name"' in content

    def test_creates_directory_if_needed(self):
        with tempfile.TemporaryDirectory() as td:
            subdir = os.path.join(td, "nested", "project")
            result = init_project(subdir)
            assert result.created is True
            assert os.path.exists(result.path)

    def test_result_dataclass_defaults(self):
        r = InitResult()
        assert r.created is False
        assert r.path == ""
        assert r.error == ""
        assert r.already_exists is False


# ═══════════════════════════════════════════════════════════════════════════
# load_project_config
# ═══════════════════════════════════════════════════════════════════════════


class TestLoadProjectConfig:
    """Tests for load_project_config()."""

    def test_returns_empty_dict_when_no_file(self):
        with tempfile.TemporaryDirectory() as td:
            result = load_project_config(td)
            assert result == {}

    def test_loads_existing_project_toml(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            init_project(td, name="test-server")
            result = load_project_config(td)
            assert result.get("project", {}).get("name") == "test-server"

    def test_loads_profiles(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            init_project(td)
            result = load_project_config(td)
            profiles = result.get("profiles", {})
            assert "default" in profiles
            assert "quick" in profiles
            assert "full" in profiles

    def test_default_profile_steps(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            init_project(td)
            result = load_project_config(td)
            default = result["profiles"]["default"]
            assert "convert" in default["steps"]
            assert "fix" in default["steps"]

    def test_quick_profile_is_minimal(self):
        pytest.importorskip("tomllib")
        with tempfile.TemporaryDirectory() as td:
            init_project(td)
            result = load_project_config(td)
            quick = result["profiles"]["quick"]
            assert quick["steps"] == ["convert", "fix"]
            assert quick["html_diff"] is False


# ═══════════════════════════════════════════════════════════════════════════
# get_profile
# ═══════════════════════════════════════════════════════════════════════════


class TestGetProfile:
    """Tests for get_profile()."""

    def test_returns_matching_profile(self):
        config = {"profiles": {"default": {"steps": ["convert"]}}}
        assert get_profile(config, "default") == {"steps": ["convert"]}

    def test_returns_empty_for_missing_profile(self):
        config = {"profiles": {"default": {"steps": ["convert"]}}}
        assert get_profile(config, "nonexistent") == {}

    def test_returns_empty_when_no_profiles_section(self):
        config = {"project": {"name": "test"}}
        assert get_profile(config, "default") == {}

    def test_returns_default_when_no_name_given(self):
        config = {"profiles": {"default": {"verbose": True}}}
        assert get_profile(config) == {"verbose": True}
