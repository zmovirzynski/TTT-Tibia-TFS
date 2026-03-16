"""
Asserts customizados para testes de scripts OTServ.
"""

def assertPlayerHasLevel(player, min_level):
    assert player["level"] >= min_level, f"Player level {player['level']} < {min_level}"

def assertCreatureAlive(creature):
    assert creature["health"] > 0, f"Creature {creature['name']} is dead"

def assertItemCount(item, expected):
    assert item["count"] == expected, f"Item count {item['count']} != {expected}"

def assertPositionEqual(pos1, pos2):
    assert pos1 == pos2, f"Position {pos1} != {pos2}"
