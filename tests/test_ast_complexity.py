# tests/test_ast_complexity.py
import pytest

luaparser = pytest.importorskip("luaparser", reason="luaparser not installed")

from ttt.converters.ast_complexity import compute_file_complexity  # noqa: E402

SIMPLE_LUA = """
function onUse(player, item, fromPosition, target, toPosition)
    player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, "hello")
    return true
end
"""

BRANCHY_LUA = """
function doHeal(cid, amount)
    if not isPlayer(cid) then return false end
    if amount > 100 then
        amount = 100
    elseif amount < 0 then
        amount = 0
    end
    for i = 1, amount do
        if i > 50 then break end
    end
    return true
end
"""

NESTED_LUA = """
function complex(cid)
    if isPlayer(cid) then
        for i = 1, 10 do
            if i > 5 then
                while true do
                    if i == 7 then break end
                end
            end
        end
    end
end
"""


def test_simple_function_low_complexity():
    metrics = compute_file_complexity(SIMPLE_LUA)
    assert len(metrics) == 1
    fn = metrics[0]
    assert fn.name == "onUse"
    assert fn.cyclomatic == 1  # no branches
    assert fn.nesting_depth == 0


def test_branchy_function_complexity():
    metrics = compute_file_complexity(BRANCHY_LUA)
    assert len(metrics) == 1
    fn = metrics[0]
    assert fn.name == "doHeal"
    assert fn.cyclomatic >= 4  # multiple branches
    assert fn.rating in ("MEDIUM", "HIGH")


def test_nesting_depth():
    metrics = compute_file_complexity(NESTED_LUA)
    assert len(metrics) == 1
    fn = metrics[0]
    assert fn.nesting_depth >= 4


def test_multiple_functions():
    code = SIMPLE_LUA + "\n" + BRANCHY_LUA
    metrics = compute_file_complexity(code)
    assert len(metrics) == 2
    names = {m.name for m in metrics}
    assert names == {"onUse", "doHeal"}


def test_empty_file_returns_empty():
    assert compute_file_complexity("") == []


def test_fallback_on_parse_error():
    # Invalid Lua should not raise — returns empty list
    result = compute_file_complexity("function (((broken")
    assert isinstance(result, list)
