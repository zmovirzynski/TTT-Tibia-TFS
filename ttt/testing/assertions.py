"""Asserts customizados para testes de scripts OTServ."""

from typing import Optional


def _assert_or_unittest(test_case, condition: bool, message: str):
    if test_case is not None:
        test_case.assertTrue(condition, message)
    elif not condition:
        raise AssertionError(message)


def assertPlayerHasLevel(player, min_level: int, test_case: Optional[object] = None):
    """Valida se player atende ao nível mínimo."""
    level = player.getLevel() if hasattr(player, "getLevel") else getattr(player, "level", None)
    _assert_or_unittest(
        test_case,
        level is not None and level >= min_level,
        f"Player level {level} < {min_level}",
    )


def assertCreatureAlive(creature, test_case: Optional[object] = None):
    """Valida se creature está viva (health > 0)."""
    if hasattr(creature, "isAlive"):
        alive = creature.isAlive()
    else:
        health = getattr(creature, "health", None)
        alive = health is not None and health > 0

    name = creature.getName() if hasattr(creature, "getName") else getattr(creature, "name", "unknown")
    _assert_or_unittest(test_case, alive, f"Creature {name} is dead")


def assertItemCount(item, expected: int, test_case: Optional[object] = None):
    """Valida quantidade de um item mock."""
    count = getattr(item, "count", None)
    _assert_or_unittest(
        test_case,
        count == expected,
        f"Item count {count} != {expected}",
    )


def assertPositionEqual(pos1, pos2, test_case: Optional[object] = None):
    """Valida igualdade de posição (x, y, z)."""
    _assert_or_unittest(test_case, pos1 == pos2, f"Position {pos1} != {pos2}")


def assertMessageSent(player, contains: str, test_case: Optional[object] = None):
    """Valida se uma mensagem contendo texto foi enviada ao player."""
    messages = getattr(player, "messages", [])
    ok = any(contains in msg for msg in messages)
    _assert_or_unittest(
        test_case,
        ok,
        f"No player message contains '{contains}'. Messages={messages}",
    )
