import pytest
from ttt.converters.ast_dead_code import find_unused_locals, UnusedLocal

CLEAN_LUA = """
function onUse(player, item)
    local msg = "hello"
    player:sendTextMessage(MESSAGE_STATUS_CONSOLE_BLUE, msg)
    return true
end
"""

UNUSED_VAR_LUA = """
function doSomething(cid)
    local unused = 42
    local used = getPlayerLevel(cid)
    return used
end
"""

UNUSED_FUNC_LUA = """
local function helper()
    return 1
end

local function alsoUnused()
    return 2
end

function onLogin(player)
    return true
end
"""

USED_FUNC_LUA = """
local function helper()
    return 1
end

function onLogin(player)
    local x = helper()
    return x > 0
end
"""


def test_clean_code_no_unused():
    result = find_unused_locals(CLEAN_LUA)
    assert result == []


def test_detects_unused_variable():
    result = find_unused_locals(UNUSED_VAR_LUA)
    names = {u.name for u in result}
    assert "unused" in names
    assert "used" not in names


def test_detects_unused_local_functions():
    result = find_unused_locals(UNUSED_FUNC_LUA)
    names = {u.name for u in result}
    assert "helper" in names
    assert "alsoUnused" in names


def test_used_local_function_not_flagged():
    result = find_unused_locals(USED_FUNC_LUA)
    names = {u.name for u in result}
    assert "helper" not in names


def test_returns_empty_on_parse_error():
    result = find_unused_locals("function (((broken")
    assert result == []


def test_unused_local_has_metadata():
    result = find_unused_locals(UNUSED_VAR_LUA)
    assert len(result) >= 1
    u = next(r for r in result if r.name == "unused")
    assert u.scope_level >= 0
    assert u.kind in ("variable", "function")
