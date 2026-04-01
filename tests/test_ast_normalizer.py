import os
import tempfile
import pytest

luaparser = pytest.importorskip("luaparser", reason="luaparser not installed")

from ttt.converters.ast_normalizer import normalize_ast_structure, structural_similarity  # noqa: E402

FUNC_A = """
function onUseSword(player, item, fromPosition, target, toPosition)
    local level = getPlayerLevel(player)
    if level < 50 then
        doPlayerSendTextMessage(player, 22, "Too low level")
        return false
    end
    return true
end
"""

FUNC_B = """
function onUseShield(cid, item, fromPos, target, toPos)
    local lvl = getPlayerLevel(cid)
    if lvl < 50 then
        doPlayerSendTextMessage(cid, 22, "Too low level")
        return false
    end
    return true
end
"""

FUNC_DIFFERENT = """
function onLogin(player)
    player:sendTextMessage(MESSAGE_INFO_DESCR, "Welcome!")
    return true
end
"""


def test_renamed_vars_are_structural_duplicates():
    score = structural_similarity(FUNC_A, FUNC_B)
    assert score >= 0.85, f"Expected high similarity, got {score}"


def test_different_functions_are_not_similar():
    score = structural_similarity(FUNC_A, FUNC_DIFFERENT)
    assert score < 0.6, f"Expected low similarity, got {score}"


def test_identical_code_is_100_percent_similar():
    score = structural_similarity(FUNC_A, FUNC_A)
    assert score == 1.0


def test_normalize_returns_string():
    result = normalize_ast_structure(FUNC_A)
    assert isinstance(result, str)
    assert len(result) > 0


def test_normalize_strips_variable_names():
    norm_a = normalize_ast_structure(FUNC_A)
    norm_b = normalize_ast_structure(FUNC_B)
    assert norm_a == norm_b


def test_normalize_returns_empty_string_on_parse_error():
    result = normalize_ast_structure("function (((broken")
    assert result == ""


# --- detect_semantic_duplicates tests ---
from ttt.analyzer.duplicates import detect_semantic_duplicates  # noqa: E402

SWORD_SCRIPT = FUNC_A
SHIELD_SCRIPT = FUNC_B
LOGIN_SCRIPT = FUNC_DIFFERENT


def test_detect_semantic_duplicates_finds_similar_files():
    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = os.path.join(tmpdir, "sword.lua")
        p2 = os.path.join(tmpdir, "shield.lua")
        p3 = os.path.join(tmpdir, "login.lua")
        for path, content in [
            (p1, SWORD_SCRIPT),
            (p2, SHIELD_SCRIPT),
            (p3, LOGIN_SCRIPT),
        ]:
            with open(path, "w") as f:
                f.write(content)

        results = detect_semantic_duplicates([p1, p2, p3], threshold=0.80)
        file_pairs = {
            (os.path.basename(r.file_a), os.path.basename(r.file_b)) for r in results
        }
        assert ("sword.lua", "shield.lua") in file_pairs


def test_no_duplicates_when_all_different():
    with tempfile.TemporaryDirectory() as tmpdir:
        p1 = os.path.join(tmpdir, "a.lua")
        p2 = os.path.join(tmpdir, "b.lua")
        with open(p1, "w") as f:
            f.write(SWORD_SCRIPT)
        with open(p2, "w") as f:
            f.write(LOGIN_SCRIPT)

        results = detect_semantic_duplicates([p1, p2], threshold=0.90)
        assert results == []
