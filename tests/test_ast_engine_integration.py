# tests/test_ast_engine_integration.py
"""Integration tests for AST backend in AnalyzeEngine."""

import os
import tempfile
import pytest

luaparser = pytest.importorskip("luaparser", reason="luaparser not installed")

from ttt.analyzer.engine import AnalyzeEngine, format_analysis_text

SWORD_LUA = """
function onUseSword(player, item, fromPos, target, toPos)
    local level = getPlayerLevel(player)
    if level < 50 then
        doPlayerSendTextMessage(player, 22, "Too low level")
        return false
    end
    return true
end
"""

SHIELD_LUA = """
function onUseShield(cid, item, fromPos, target, toPos)
    local lvl = getPlayerLevel(cid)
    if lvl < 50 then
        doPlayerSendTextMessage(cid, 22, "Too low level")
        return false
    end
    return true
end
"""


@pytest.fixture
def lua_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        for name, content in [("sword.lua", SWORD_LUA), ("shield.lua", SHIELD_LUA)]:
            with open(os.path.join(tmpdir, name), "w") as f:
                f.write(content)
        yield tmpdir


def test_engine_runs_with_use_ast(lua_dir):
    engine = AnalyzeEngine(use_ast=True)
    report = engine.analyze(lua_dir)
    assert report is not None


def test_ast_report_has_semantic_duplicates(lua_dir):
    engine = AnalyzeEngine(use_ast=True)
    report = engine.analyze(lua_dir)
    # semantic_duplicates is a new field
    assert hasattr(report, "semantic_duplicates")
    assert len(report.semantic_duplicates) >= 1


def test_ast_report_text_includes_semantic_section(lua_dir):
    engine = AnalyzeEngine(use_ast=True)
    report = engine.analyze(lua_dir)
    text = format_analysis_text(report)
    assert "semantic" in text.lower() or "duplicate" in text.lower()


def test_engine_without_ast_still_works(lua_dir):
    engine = AnalyzeEngine(use_ast=False)
    report = engine.analyze(lua_dir)
    assert report is not None
    assert report.semantic_duplicates == []
