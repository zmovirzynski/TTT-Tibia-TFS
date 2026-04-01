import pytest

luaparser = pytest.importorskip("luaparser", reason="luaparser not installed")

from ttt.analyzers.ast_enricher import enrich_analysis  # noqa: E402
from ttt.analyzers.lua_oop_analyzer import LuaFileAnalysis  # noqa: E402

COMPLEX_LUA = """
function bigFunc(cid, amount)
    if not isPlayer(cid) then return false end
    if amount > 100 then
        amount = 100
    elseif amount < 0 then
        amount = 0
    end
    for i = 1, amount do
        if i > 50 then
            doPlayerSendTextMessage(cid, 22, tostring(i))
        end
    end
    local unused = "dead"
    return true
end
"""

SIMPLE_LUA = """
function onLogin(player)
    return true
end
"""


def test_enrich_produces_metrics():
    analysis = LuaFileAnalysis(file_path="test.lua", total_lines=20)
    enriched = enrich_analysis(analysis, COMPLEX_LUA)
    assert enriched.ast_metrics is not None
    m = enriched.ast_metrics
    assert m.max_complexity >= 4
    assert m.max_nesting >= 2
    assert len(m.function_metrics) >= 1


def test_unused_locals_detected():
    analysis = LuaFileAnalysis(file_path="test.lua", total_lines=20)
    enriched = enrich_analysis(analysis, COMPLEX_LUA)
    assert enriched.ast_metrics is not None
    assert len(enriched.ast_metrics.unused_locals) >= 1
    names = {u.name for u in enriched.ast_metrics.unused_locals}
    assert "unused" in names


def test_simple_function_low_complexity():
    analysis = LuaFileAnalysis(file_path="simple.lua", total_lines=3)
    enriched = enrich_analysis(analysis, SIMPLE_LUA)
    assert enriched.ast_metrics is not None
    assert enriched.ast_metrics.max_complexity == 1


def test_enrich_returns_same_object():
    analysis = LuaFileAnalysis(file_path="x.lua", total_lines=5)
    result = enrich_analysis(analysis, SIMPLE_LUA)
    assert result is analysis


def test_enrich_does_not_raise_on_bad_lua():
    analysis = LuaFileAnalysis(file_path="bad.lua", total_lines=1)
    result = enrich_analysis(analysis, "function (((")
    assert result.ast_metrics is not None
    assert result.ast_metrics.max_complexity == 0


def test_guidelines_include_ast_complexity():
    from ttt.analyzers.lua_oop_analyzer import LuaOopAnalyzer
    from ttt.analyzers.guidelines_generator import GuidelinesGenerator

    analyzer = LuaOopAnalyzer()
    analysis = analyzer.analyze_content(COMPLEX_LUA, "action.lua")
    enrich_analysis(analysis, COMPLEX_LUA)

    gen = GuidelinesGenerator()
    output = gen.generate([analysis])

    assert "cyclomatic" in output.lower() or "complexity" in output.lower()
